"""Materialize built-in skills into the sandbox, install deps, and execute them."""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from sandbox.core import Sandbox
from settings import settings

from agent_team.skills.loader import (
    Skill,
    _load_skill,
    find_skill,
    sandbox_skills_dir,
)

_DEPS_SENTINEL = ".deps_installed"
_sandbox_client: Sandbox | None = None


def _client() -> Sandbox:
    global _sandbox_client
    if _sandbox_client is None:
        _sandbox_client = Sandbox(settings.SANDBOX_DIR)
    return _sandbox_client


def materialize_into_sandbox(skill: Skill) -> Skill:
    """Copy a built-in skill into the sandbox; return the sandbox-resident Skill."""
    if skill.source == "sandbox":
        return skill
    target = sandbox_skills_dir() / skill.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(skill.path, target)
    return _load_skill(target, "sandbox")


def install_dependencies(skill: Skill, *, force: bool = False) -> dict:
    """Install ``requirements.txt`` (if present) into the host Python environment.

    Pip runs *outside* the sandbox because the launcher delegates to ``sys.executable``
    on the host, so packages must be importable from the host venv.
    """
    req_file = skill.path / "requirements.txt"
    if not req_file.is_file():
        return {"installed": False, "reason": "no requirements.txt"}

    sentinel = skill.path / _DEPS_SENTINEL
    if sentinel.exists() and not force:
        return {"installed": False, "reason": "already installed", "sentinel": str(sentinel)}

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {
            "installed": False,
            "error": "pip install failed",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    sentinel.write_text("ok\n", encoding="utf-8")
    return {"installed": True, "stdout": result.stdout.strip()}


def execute_skill(skill: Skill, args: str) -> dict:
    """Run the skill's entry script via the sandbox runtime."""
    if not skill.entry:
        return {"error": f"Skill {skill.name!r} is not runnable (no `entry:` in frontmatter)."}

    entry_path = (skill.path / skill.entry).resolve()
    if not entry_path.is_file():
        return {"error": f"Entry script not found: {skill.entry}"}

    sandbox = _client()
    sandbox_root = sandbox.root_dir.resolve()
    try:
        rel_entry = entry_path.relative_to(sandbox_root).as_posix()
    except ValueError:
        return {
            "error": (
                "Entry script is outside the sandbox root. "
                "Materialize the skill into the sandbox first."
            ),
            "entry_path": str(entry_path),
            "sandbox_root": str(sandbox_root),
        }

    command = f"python3 {shlex.quote(rel_entry)}"
    if args:
        command = f"{command} {args}"
    result = sandbox.run(command, check=False)
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def ensure_runnable(name: str) -> tuple[Skill | None, dict | None]:
    """Resolve a skill by name, copy into sandbox if needed, install deps."""
    skill = find_skill(name)
    if skill is None:
        return None, {"error": f"Skill not found: {name!r}"}
    skill = materialize_into_sandbox(skill)
    install_result = install_dependencies(skill)
    if install_result.get("error"):
        return skill, {"error": "Dependency installation failed", "details": install_result}
    return skill, None
