"""
Web GUI server for AtomSculptor.

Four-panel interface:
  1. Todo-flow DAG + session info
  2. Streaming chat (user ↔ agent events)
  3. 3-D atomic-structure viewer (3Dmol.js)
  4. Sandbox file explorer
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent_team.agent import root_agent
from agent_team.state import todo_flow
from settings import settings

# ── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_STATIC = _HERE / "static"

# ── ADK runner & session ─────────────────────────────────────────────────────
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name="atom_sculptor",
    session_service=session_service,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _sandbox_root() -> Path:
    return Path(settings.SANDBOX_DIR).expanduser().resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_todo_flow() -> dict:
    if todo_flow.plan is None:
        return {"tasks": [], "finished": True}
    tasks = []
    for t in todo_flow.plan.tasks:
        tasks.append({
            "id": t.id,
            "uuid": t.uuid,
            "description": t.description,
            "status": t.status.value,
            "dependencies": t.dependencies,
            "result": t.result,
        })
    return {"tasks": tasks, "finished": todo_flow.is_finished()}


def _build_file_tree(root: Path, base: Path) -> list:
    if not root.exists():
        return []
    entries = []
    try:
        for item in sorted(
            root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            rel = str(item.relative_to(base))
            if item.is_dir():
                entries.append({
                    "name": item.name,
                    "path": rel,
                    "type": "directory",
                    "children": _build_file_tree(item, base),
                })
            else:
                entries.append({
                    "name": item.name,
                    "path": rel,
                    "type": "file",
                    "size": item.stat().st_size,
                })
    except PermissionError:
        pass
    return entries


def _safe_value(obj):
    """Recursively convert protobuf / special objects to plain JSON-safe types."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_value(v) for v in obj]
    try:
        return {str(k): _safe_value(v) for k, v in dict(obj).items()}
    except (TypeError, ValueError):
        return str(obj)


def _event_to_messages(event) -> list[dict]:
    """Convert a single google-adk Event into a list of UI message dicts."""
    messages = []
    author = getattr(event, "author", "unknown")
    content = getattr(event, "content", None)
    if content is None:
        return messages
    parts = getattr(content, "parts", None) or []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            messages.append({
                "type": "agent_message",
                "author": author,
                "text": text,
                "timestamp": _now(),
            })
        fc = getattr(part, "function_call", None)
        if fc:
            messages.append({
                "type": "tool_call",
                "author": author,
                "tool": getattr(fc, "name", "unknown"),
                "args": _safe_value(getattr(fc, "args", {})),
                "timestamp": _now(),
            })
        fr = getattr(part, "function_response", None)
        if fr:
            messages.append({
                "type": "tool_result",
                "author": author,
                "tool": getattr(fr, "name", "unknown"),
                "result": _safe_value(getattr(fr, "response", {})),
                "timestamp": _now(),
            })
    return messages


def _is_path_safe(requested: Path, root: Path) -> bool:
    try:
        requested.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


async def _send_json_or_stop(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except WebSocketDisconnect:
        return False
    except RuntimeError as exc:
        if 'Cannot call "send" once a close message has been sent.' in str(exc):
            return False
        raise


async def _close_websocket_quietly(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except (RuntimeError, WebSocketDisconnect):
        pass


# 3Dmol.js natively understands these formats
_THREEMOL_NATIVE = {"xyz", "cif", "pdb", "sdf", "mol2"}
_EXT_TO_FMT = {
    ".xyz": "xyz", ".cif": "cif", ".pdb": "pdb",
    ".vasp": "vasp", ".poscar": "vasp", ".extxyz": "xyz",
    ".mol2": "mol2", ".sdf": "sdf",
}


# ── HTTP routes ──────────────────────────────────────────────────────────────

async def index(request):
    return FileResponse(_STATIC / "index.html", media_type="text/html")


async def api_todo_flow(request):
    return JSONResponse(_serialize_todo_flow())


async def api_files(request):
    root = _sandbox_root()
    return JSONResponse({"tree": _build_file_tree(root, root), "root": str(root)})


async def api_file_content(request):
    rel = request.query_params.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = _sandbox_root()
    fp = (root / rel).resolve()
    if not _is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        return JSONResponse({"content": fp.read_text("utf-8"), "path": rel})
    except UnicodeDecodeError:
        return JSONResponse({"error": "binary file"}, status_code=400)


async def api_structure(request):
    rel = request.query_params.get("path", "")
    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = _sandbox_root()
    fp = (root / rel).resolve()
    if not _is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)
    if not fp.exists() or not fp.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    fmt = _EXT_TO_FMT.get(fp.suffix.lower(), "xyz")
    try:
        content = fp.read_text("utf-8")
    except UnicodeDecodeError:
        return JSONResponse({"error": "binary file"}, status_code=400)

    # Convert non-native formats via ASE so 3Dmol can render them
    if fmt not in _THREEMOL_NATIVE:
        try:
            from ase.io import read as ase_read, write as ase_write
            atoms = ase_read(str(fp))
            sio = StringIO()
            ase_write(sio, atoms, format="extxyz")
            content = sio.getvalue()
            fmt = "xyz"
        except Exception:
            pass  # fall through with raw content

    return JSONResponse({"content": content, "format": fmt, "path": rel})


# ── WebSocket ────────────────────────────────────────────────────────────────

async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    user_id = "web_user"

    # Create ADK session
    try:
        session = await session_service.create_session(
            app_name="atom_sculptor",
            user_id=user_id,
        )
        session_id = getattr(session, "id", None) or getattr(
            session, "session_id", f"ws_{id(websocket)}"
        )
    except Exception as exc:
        if await _send_json_or_stop(
            websocket, {"type": "error", "text": f"Session error: {exc}"}
        ):
            await _close_websocket_quietly(websocket)
        return

    # Push initial state
    if not await _send_json_or_stop(
        websocket, {"type": "todo_flow_update", "data": _serialize_todo_flow()}
    ):
        return
    if not await _send_json_or_stop(
        websocket,
        {
            "type": "files_update",
            "data": _build_file_tree(_sandbox_root(), _sandbox_root()),
        },
    ):
        return

    try:
        while True:
            raw = await websocket.receive_json()
            kind = raw.get("type")

            if kind == "chat":
                user_text = raw.get("message", "").strip()
                if not user_text:
                    continue

                # Echo user message
                if not await _send_json_or_stop(
                    websocket,
                    {
                        "type": "user_message",
                        "text": user_text,
                        "timestamp": _now(),
                    },
                ):
                    return

                try:
                    content = types.Content(
                        role="user",
                        parts=[types.Part(text=user_text)],
                    )
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=content,
                    ):
                        for msg in _event_to_messages(event):
                            if not await _send_json_or_stop(websocket, msg):
                                return
                        if not await _send_json_or_stop(
                            websocket,
                            {
                                "type": "todo_flow_update",
                                "data": _serialize_todo_flow(),
                            },
                        ):
                            return

                    # Agent turn finished
                    if not await _send_json_or_stop(websocket, {"type": "done"}):
                        return
                    if not await _send_json_or_stop(
                        websocket,
                        {
                            "type": "files_update",
                            "data": _build_file_tree(_sandbox_root(), _sandbox_root()),
                        },
                    ):
                        return
                except WebSocketDisconnect:
                    return
                except Exception as exc:
                    if not await _send_json_or_stop(
                        websocket,
                        {
                            "type": "error",
                            "text": str(exc),
                            "traceback": traceback.format_exc(),
                        },
                    ):
                        return

            elif kind == "refresh_files":
                if not await _send_json_or_stop(
                    websocket,
                    {
                        "type": "files_update",
                        "data": _build_file_tree(_sandbox_root(), _sandbox_root()),
                    },
                ):
                    return

            elif kind == "refresh_todo":
                if not await _send_json_or_stop(
                    websocket,
                    {
                        "type": "todo_flow_update",
                        "data": _serialize_todo_flow(),
                    },
                ):
                    return

    except WebSocketDisconnect:
        pass


# ── Starlette app ────────────────────────────────────────────────────────────

app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/todo-flow", api_todo_flow),
        Route("/api/files", api_files),
        Route("/api/file-content", api_file_content),
        Route("/api/structure", api_structure),
        WebSocketRoute("/ws", ws_chat),
        Mount("/static", StaticFiles(directory=str(_STATIC)), name="static"),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
)


def run_server(host: str = "0.0.0.0", port: int = 8000):
    print(f"\n  AtomSculptor Web GUI  →  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")
