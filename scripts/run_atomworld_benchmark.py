#!/usr/bin/env python3
"""AtomWorldBench client adapter for AtomSculptor.

This script is intentionally only a client of an already-running AtomWorldBench
API server. It does not start the benchmark server, generate datasets, or own
benchmark infrastructure.

Its responsibilities are isolated into three layers:
1. AtomWorldBench HTTP client: create or attach to a benchmark session,
   fetch tasks, submit results, and retrieve evaluation output.
2. Per-task workspace isolation: materialize one task at a time inside a
   dedicated sandbox directory so agent-side files never leak across tasks.
3. AtomSculptor execution adapter: present one task to the local agent in a
   constrained prompt, require a single output structure file, and convert that
   file back to CIF for submission.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _ensure_project_root_on_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_ensure_project_root_on_path()


@dataclass(frozen=True)
class AtomWorldTask:
    task_id: str
    action_prompt: str
    input_cif: str


@dataclass(frozen=True)
class TaskWorkspace:
    task_dir: Path
    input_path: Path
    output_path: Path
    output_cif_path: Path
    log_path: Path


class AtomWorldClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def create_session(self, action_name: str, limit: int, repeat: int) -> str:
        response = self._request(
            "POST",
            "/sessions",
            payload={
                "action_name": action_name,
                "limit": limit,
                "repeat": repeat,
            },
        )
        if not isinstance(response, dict) or "session_id" not in response:
            raise RuntimeError(f"Unexpected session response: {response}")
        return str(response["session_id"])

    def list_tasks(self, session_id: str) -> list[dict[str, Any]]:
        response = self._request("GET", f"/sessions/{session_id}/tasks")
        if not isinstance(response, list):
            raise RuntimeError(f"Unexpected task list response: {response}")
        return response

    def fetch_task(self, session_id: str, task_id: str) -> AtomWorldTask:
        response = self._request(
            "GET",
            f"/sessions/{session_id}/tasks/{urllib.parse.quote(task_id)}",
        )
        if not isinstance(response, dict):
            raise RuntimeError(f"Unexpected task response for {task_id}: {response}")
        return AtomWorldTask(
            task_id=str(response["task_id"]),
            action_prompt=str(response["action_prompt"]),
            input_cif=str(response["input_cif"]),
        )

    def submit_task_result(
        self,
        session_id: str,
        task_id: str,
        result_cif: str,
        elapsed_seconds: float,
    ) -> None:
        self._request(
            "POST",
            f"/sessions/{session_id}/tasks/{urllib.parse.quote(task_id)}/submit",
            payload={
                "result_cif": result_cif,
                "elapsed_seconds": elapsed_seconds,
            },
        )

    def trigger_evaluation(self, session_id: str) -> None:
        self._request("POST", f"/sessions/{session_id}/evaluate", payload={})

    def fetch_results(self, session_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/sessions/{session_id}/results")
        if not isinstance(response, dict):
            raise RuntimeError(f"Unexpected results response: {response}")
        return response

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

        if not body.strip():
            return {}
        return json.loads(body)


class WorkspaceFactory:
    def __init__(self, sandbox_root: Path, sessions_dir_name: str) -> None:
        self.sandbox_root = sandbox_root.resolve()
        self.sessions_root = (self.sandbox_root / sessions_dir_name).resolve()
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    def prepare(self, session_id: str, task: AtomWorldTask) -> TaskWorkspace:
        task_dir = self.sessions_root / self._safe_name(session_id) / self._safe_name(task.task_id)
        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)

        workspace = TaskWorkspace(
            task_dir=task_dir,
            input_path=task_dir / "input.cif",
            output_path=task_dir / "result.extxyz",
            output_cif_path=task_dir / "result.cif",
            log_path=task_dir / "agent_log.txt",
        )
        workspace.input_path.write_text(task.input_cif, encoding="utf-8")
        return workspace

    def cleanup(self, workspace: TaskWorkspace) -> None:
        shutil.rmtree(workspace.task_dir)

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        return cleaned or "task"


class AtomSculptorExecutor:
    def __init__(self, sandbox_root: Path, user_id: str, app_name: str = "agents") -> None:
        self.sandbox_root = sandbox_root.resolve()
        self.user_id = user_id
        self.app_name = app_name

        os.environ["SANDBOX_DIR"] = str(self.sandbox_root)
        self.Runner, self.InMemorySessionService, self.types_module, self.root_agent, self.get_context = (
            self._load_runner_components()
        )

    def run_task(self, task: AtomWorldTask, workspace: TaskWorkspace) -> tuple[str, float, list[str]]:
        prompt = self._build_prompt(task, workspace)
        started_at = time.perf_counter()
        log_lines = asyncio.run(self._run_agent_once(prompt))
        elapsed_seconds = time.perf_counter() - started_at

        self._write_log(workspace.log_path, log_lines)
        if not workspace.output_path.exists():
            raise RuntimeError(
                f"Agent did not write the required output file for {task.task_id}: {workspace.output_path}\n"
                f"See log: {workspace.log_path}"
            )

        result_cif = self._convert_structure_to_cif(workspace.output_path, workspace.output_cif_path)
        return result_cif, elapsed_seconds, log_lines

    def _build_prompt(self, task: AtomWorldTask, workspace: TaskWorkspace) -> str:
        input_rel = self._relative_to_sandbox(workspace.input_path)
        output_rel = self._relative_to_sandbox(workspace.output_path)
        return (
            # "You are solving exactly one AtomWorldBench task.\n"
            # f"Task id: {task.task_id}\n"
            f"Input structure path: {input_rel}\n"
            f"Required output path: {output_rel}\n\n"
            # "Instruction to apply exactly once:\n"
            f"{task.action_prompt}\n\n"
            "Constraints:\n"
            "- Work only from the provided input structure file.\n"
            # "- Do not use web search, external datasets, or external references.\n"
            "- Do not ask clarification questions.\n"
            "- Write exactly one final structure file to the required output path.\n"
            # "- Write the output in extxyz format.\n"
            "- Finish after that file is written.\n"
        )

    def _relative_to_sandbox(self, path: Path) -> str:
        return path.resolve().relative_to(self.sandbox_root).as_posix()

    @staticmethod
    def _load_runner_components() -> tuple[Any, Any, Any, Any, Any]:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        from agent_team.agent import root_agent
        from agent_team.context import get_context

        return Runner, InMemorySessionService, types, root_agent, get_context

    async def _run_agent_once(self, prompt: str) -> list[str]:
        self.get_context().reset()
        session_service = self.InMemorySessionService()
        runner = self.Runner(
            agent=self.root_agent,
            app_name=self.app_name,
            session_service=session_service,
            auto_create_session=True,
        )

        session = await session_service.create_session(app_name=self.app_name, user_id=self.user_id)
        session_id = getattr(session, "id", None) or getattr(session, "session_id", None)
        if not session_id:
            raise RuntimeError("ADK session creation did not return an id")

        message = self.types_module.Content(role="user", parts=[self.types_module.Part(text=prompt)])
        log_lines: list[str] = []
        async for event in runner.run_async(user_id=self.user_id, session_id=session_id, new_message=message):
            author = getattr(event, "author", "unknown")
            content = getattr(event, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", None) or []:
                text = getattr(part, "text", None)
                if text:
                    log_lines.append(f"[{author}] {text}")
                function_call = getattr(part, "function_call", None)
                if function_call is not None:
                    log_lines.append(
                        f"[{author}] TOOL {getattr(function_call, 'name', 'unknown')} {getattr(function_call, 'args', {})}"
                    )
                function_response = getattr(part, "function_response", None)
                if function_response is not None:
                    log_lines.append(
                        f"[{author}] RESULT {getattr(function_response, 'name', 'unknown')} {getattr(function_response, 'response', {})}"
                    )
        return log_lines

    @staticmethod
    def _write_log(log_path: Path, lines: list[str]) -> None:
        log_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _convert_structure_to_cif(source_path: Path, output_cif_path: Path) -> str:
        from ase.io import read as ase_read
        from ase.io import write as ase_write
        from web_gui.structure import resolve_ase_io_format

        detected_format = resolve_ase_io_format(source_path)
        atoms = ase_read(str(source_path), format=detected_format) if detected_format else ase_read(str(source_path))
        ase_write(str(output_cif_path), atoms, format="cif")
        return output_cif_path.read_text(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use AtomSculptor as a client of an existing AtomWorldBench API server.",
    )
    parser.add_argument("--base-url", required=True, help="AtomWorldBench server base URL, local or remote")
    parser.add_argument("--api-key", required=True, help="Value for the X-API-Key header")
    parser.add_argument("--session-id", help="Use an existing AtomWorldBench session instead of creating a new one")
    parser.add_argument("--action-name", help="Action name for a new benchmark session")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of tasks to request when creating a session")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat count when creating a session")
    parser.add_argument("--sandbox-dir", default="sandbox/.benchmark", help="Sandbox root used only for per-task benchmark files")
    parser.add_argument("--sessions-dir", default="benchmark_runs", help="Directory under the sandbox root for isolated task workspaces")
    parser.add_argument("--user-id", default="atomworld_benchmark", help="ADK user id used for local AtomSculptor execution")
    parser.add_argument("--keep-session-files", action="store_true", help="Keep per-task files and logs after submission")
    parser.add_argument("--skip-evaluate", action="store_true", help="Submit all tasks but do not trigger server-side evaluation")
    args = parser.parse_args()

    if not args.session_id and not args.action_name:
        parser.error("either --session-id or --action-name is required")
    if args.session_id and args.action_name:
        parser.error("use either --session-id or --action-name, not both")
    return args


def print_progress(index: int, total: int, task_id: str) -> None:
    print(f"[{index}/{total}] {task_id}", flush=True)


def resolve_session_id(args: argparse.Namespace, client: AtomWorldClient) -> str:
    if args.session_id:
        return str(args.session_id)
    return client.create_session(action_name=args.action_name, limit=args.limit, repeat=args.repeat)


def main() -> int:
    args = parse_args()
    client = AtomWorldClient(base_url=args.base_url, api_key=args.api_key)
    session_id = resolve_session_id(args, client)
    print(f"Benchmark session: {session_id}", flush=True)

    sandbox_root = Path(args.sandbox_dir).resolve()
    workspace_factory = WorkspaceFactory(sandbox_root=sandbox_root, sessions_dir_name=args.sessions_dir)
    executor = AtomSculptorExecutor(sandbox_root=sandbox_root, user_id=args.user_id)

    task_metas = client.list_tasks(session_id)
    if not task_metas:
        print("No tasks returned by the benchmark server.", flush=True)
        return 0

    for index, task_meta in enumerate(task_metas, start=1):
        task_id = str(task_meta["task_id"])
        print_progress(index, len(task_metas), task_id)
        task = client.fetch_task(session_id, task_id)
        workspace = workspace_factory.prepare(session_id, task)

        try:
            result_cif, elapsed_seconds, _ = executor.run_task(task, workspace)
            client.submit_task_result(
                session_id=session_id,
                task_id=task.task_id,
                result_cif=result_cif,
                elapsed_seconds=elapsed_seconds,
            )
        finally:
            if not args.keep_session_files:
                workspace_factory.cleanup(workspace)

    if args.skip_evaluate:
        return 0

    client.trigger_evaluation(session_id)
    results = client.fetch_results(session_id)
    print(json.dumps(results, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)