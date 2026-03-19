import base64
import os
import shlex
import subprocess
from pathlib import Path

from sandbox.core import Sandbox, SandboxRuntimeError
from settings import settings

from google.adk.tools.base_toolset import BaseToolset


_sandbox: Sandbox | None = None


def _sandbox_client() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox(settings.SANDBOX_DIR)
    return _sandbox


def _sandbox_root() -> Path:
    return Path(settings.SANDBOX_DIR).resolve()


def _run_args(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    sandbox = _sandbox_client()
    sandbox.ensure_runtime()
    command_str = shlex.join(args)

    result = subprocess.run(
        ["srt", "--settings", str(sandbox.settings_path), command_str],
        cwd=str(sandbox.root_dir),
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )

    if check and result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(message)

    return result


def _normalize_result_path(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def sandbox_status() -> dict:
    """
    Returns information about the sandbox environment, including:
    - sandbox_root: the absolute path to the sandbox root directory
    - exists: whether the sandbox root directory currently exists
    - runtime_available: whether the sandbox runtime is currently available
    - runtime_error: if the runtime is not available, an error message describing the issue
    """
    root = _sandbox_root()
    runtime_available = True
    runtime_error = ""

    try:
        _sandbox_client().ensure_runtime()
    except SandboxRuntimeError as error:
        runtime_available = False
        runtime_error = str(error)

    return {
        "sandbox_root": str(root),
        "exists": root.exists(),
        "runtime_available": runtime_available,
        "runtime_error": runtime_error,
    }


def sandbox_list_files(path: str = ".", recursive: bool = True) -> dict:
    """Lists files in the specified directory within the sandbox."""
    requested_path = path or "."
    script = """
from pathlib import Path
import sys

target = Path(sys.argv[1])
recursive = sys.argv[2] == "1"

if not target.exists():
    raise SystemExit(0)

if target.is_file():
    print(target.as_posix())
    raise SystemExit(0)

iterator = target.rglob("*") if recursive else target.glob("*")
for item in sorted(p for p in iterator if p.is_file()):
    print(item.as_posix())
""".strip()
    result = _run_args(["python3", "-c", script, requested_path, "1" if recursive else "0"], check=False)

    if result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(f"Failed to list files: {message}")

    files = [
        _normalize_result_path(line)
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    return {
        "files": sorted(files)
    }


def sandbox_read_file(path: str) -> dict:
    """Reads the content of a file at the specified path within the sandbox."""
    script = """
from pathlib import Path
import sys

target = Path(sys.argv[1])
if not target.exists() or not target.is_file():
    raise SystemExit(2)

sys.stdout.write(target.read_text(encoding="utf-8"))
""".strip()
    result = _run_args(["python3", "-c", script, path], check=False)
    if result.returncode == 2:
        return {"error": f"File not found: {path}"}
    if result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        return {"error": f"Failed to read file: {message}"}
    return {"content": result.stdout}


def sandbox_write_file(path: str, content: str, overwrite: bool = True) -> dict:
    """Writes content to a file at the specified path within the sandbox."""
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    script = """
import base64
from pathlib import Path
import sys

target = Path(sys.argv[1])
overwrite = sys.argv[2] == "1"
payload = sys.argv[3]

if target.exists() and not overwrite:
    raise SystemExit(3)

target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(base64.b64decode(payload).decode("utf-8"), encoding="utf-8")
""".strip()
    result = _run_args(["python3", "-c", script, path, "1" if overwrite else "0", encoded], check=False)
    if result.returncode == 3:
        return {"error": f"File already exists: {path}"}
    if result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        return {"error": f"Failed to write file: {message}"}
    return {"result": f"{_normalize_result_path(path)} written"}


def sandbox_create_directory(path: str) -> dict:
    """Creates a directory at the specified path within the sandbox, including any necessary parent directories."""
    script = """
from pathlib import Path
import sys

Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)
""".strip()
    result = _run_args(["python3", "-c", script, path], check=False)
    if result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        return {"error": f"Failed to create directory: {message}"}
    return {"result": f"{_normalize_result_path(path)} created"}


def sandbox_delete_path(path: str, missing_ok: bool = True) -> dict:
    """Deletes a file or directory at the specified path within the sandbox."""
    script = """
from pathlib import Path
import shutil
import sys

target = Path(sys.argv[1])
missing_ok = sys.argv[2] == "1"

if not target.exists():
    raise SystemExit(0 if missing_ok else 4)

if target.is_file():
    target.unlink()
else:
    shutil.rmtree(target)
""".strip()
    result = _run_args(["python3", "-c", script, path, "1" if missing_ok else "0"], check=False)
    if result.returncode == 4:
        return {"result": False}
    if result.returncode != 0:
        message = result.stderr.strip() if result.stderr else "unknown error"
        return {"error": f"Failed to delete path: {message}"}
    return {"result": True}


def sandbox_run_command(command: str, timeout_seconds: int = 30) -> dict:
    """
    Run shell command in the sandbox runtime environment with a specified timeout. 
    Returns the command, whether it timed out, the exit code, and captured stdout and stderr.
    When using path arguments in the command, use relative paths to the sandbox root `.` instead of absolute paths.
    
    """
    if not isinstance(command, str) or not command.strip():
        return {"error": "command must be a non-empty string"}

    timeout = max(1, min(int(timeout_seconds), 120))
    sandbox = _sandbox_client()
    sandbox.ensure_runtime()

    args = ["bash", "-lc", command]
    command_str = shlex.join(args)

    try:
        result = subprocess.run(
            ["srt", "--settings", str(sandbox.settings_path), command_str],
            cwd=str(sandbox.root_dir),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else (error.stdout or "")
        stderr = error.stderr if isinstance(error.stderr, str) else (error.stderr or "")
        return {
            "command": command,
            "timed_out": True,
            "timeout_seconds": timeout,
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
        }

    return {
        "timed_out": False,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }



    