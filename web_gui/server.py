"""
Web GUI server for AtomSculptor.

Four-panel interface:
    1. Todo-flow DAG + session info
    2. Streaming chat (user ↔ agent events)
    3. 3-D atomic-structure editor (Three.js)
    4. Workspace file explorer
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse
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

STRUCTURE_EXTS = {"cif", "xyz", "vasp", "poscar", "extxyz", "pdb", "sdf", "mol2"}
VASP_STRUCTURE_PREFIXES = ("poscar", "contcar")

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


def _asset_url(relative_path: str) -> str:
    asset_path = _STATIC / relative_path
    try:
        version = asset_path.stat().st_mtime_ns
    except FileNotFoundError:
        version = 0
    return f"/static/{relative_path}?v={version}"


def _detect_ase_format(path_or_name: str | Path) -> str | None:
    name = Path(path_or_name).name.lower()
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix in STRUCTURE_EXTS:
        return "vasp" if suffix == "poscar" else suffix
    if any(
        name == prefix
        or name.startswith(f"{prefix}_")
        or name.startswith(f"{prefix}-")
        or name.startswith(f"{prefix}.")
        for prefix in VASP_STRUCTURE_PREFIXES
    ):
        return "vasp"
    return None


def _is_structure_filename(path_or_name: str | Path) -> bool:
    return _detect_ase_format(path_or_name) is not None


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
                    "is_structure": _is_structure_filename(item.name),
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




# ── HTTP routes ──────────────────────────────────────────────────────────────

async def index(request):
    html = (_STATIC / "index.html").read_text("utf-8")
    html = html.replace("__INDEX_CSS__", _asset_url("css/index.css"))
    html = html.replace("__APP_JS__", _asset_url("js/app.js"))
    return HTMLResponse(html, media_type="text/html", headers={"Cache-Control": "no-store"})


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

    try:
        from ase.io import read as ase_read
        ase_format = _detect_ase_format(fp)
        atoms = ase_read(str(fp), format=ase_format)
    except Exception as exc:
        return JSONResponse({"error": f"Could not parse structure: {exc}"}, status_code=400)

    # Collect unit cell (3x3 matrix, Angstroms) — None if not periodic
    cell = None
    # ASE returns NumPy scalar booleans here; cast to native bool for JSON.
    pbc = [bool(v) for v in atoms.get_pbc()]
    if any(pbc):
        cell = atoms.get_cell().tolist()

    atom_list = []
    for i, atom in enumerate(atoms):
        atom_list.append({
            "id": i,
            "symbol": atom.symbol,
            "x": float(atom.position[0]),
            "y": float(atom.position[1]),
            "z": float(atom.position[2]),
        })

    return JSONResponse({
        "atoms": atom_list,
        "cell": cell,
        "pbc": pbc,
        "path": rel,
    })


async def api_structure_save(request):
    """POST /api/structure/save — receive modified atom list, write back via ASE."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    rel = body.get("path", "")
    atoms_data = body.get("atoms", [])
    cell = body.get("cell", None)
    pbc = body.get("pbc", [False, False, False])

    if not rel:
        return JSONResponse({"error": "path required"}, status_code=400)
    root = _sandbox_root()
    fp = (root / rel).resolve()
    if not _is_path_safe(fp, root):
        return JSONResponse({"error": "access denied"}, status_code=403)

    try:
        from ase import Atoms as AseAtoms
        from ase.io import write as ase_write

        symbols = [a["symbol"] for a in atoms_data]
        positions = [[a["x"], a["y"], a["z"]] for a in atoms_data]
        kwargs = {"symbols": symbols, "positions": positions, "pbc": pbc}
        if cell is not None:
            kwargs["cell"] = cell
        new_atoms = AseAtoms(**kwargs)
        ase_format = _detect_ase_format(fp)
        if ase_format is None:
            ase_write(str(fp), new_atoms)
        else:
            ase_write(str(fp), new_atoms, format=ase_format)
        return JSONResponse({"ok": True, "path": rel, "natoms": len(atoms_data)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


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
        Route("/api/structure/save", api_structure_save, methods=["POST"]),
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
