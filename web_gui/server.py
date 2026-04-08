"""
Web GUI server for AtomSculptor.

Four-panel interface:
    1. Todo-flow DAG + session info
    2. Streaming chat (user ↔ agent events)
    3. 3-D atomic-structure editor (Three.js)
    4. Workspace file explorer

Submodules:
    helpers            – generic utilities (timestamps, asset URLs, path safety)
    filesystem         – sandbox root, file-tree builder
    structure          – ASE format detection, read / write
    agent_session      – ADK runner, session service, event serialisation
    todo               – todo-flow DAG serialisation
    routes             – HTTP route handlers
    websocket_handler  – WebSocket handler
"""

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .helpers import STATIC_DIR


class NoCacheJSMiddleware:
    """Force revalidation for all /static/js/ responses so stale module
    caches never cause 'export not found' errors in the browser."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith("/static/js/"):
            async def send_with_no_cache(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers = [
                        (k, v) for k, v in headers
                        if k.lower() not in (b"cache-control", b"expires", b"pragma")
                    ]
                    headers.append((b"cache-control", b"no-cache"))
                    message = {**message, "headers": headers}
                await send(message)
            await self.app(scope, receive, send_with_no_cache)
        else:
            await self.app(scope, receive, send)


from .routes import (
    index,
    api_todo_flow,
    api_reset,
    api_files,
    api_file_content,
    api_structure,
    api_structure_save,
    api_structure_export,
    api_structure_build_surface,
    api_structure_build_supercell,
    api_structure_add_molecule,
    api_structure_build_interfaces,
    api_structure_build_interfaces_save,
    api_file_delete,
    api_file_delete_many,
    api_file_rename,
    api_file_duplicate,
    api_file_paste,
    api_file_upload,
    api_sessions_list,
    api_session_rename,
    api_session_delete,
)
from .websocket_handler import ws_chat

# ── Starlette app ────────────────────────────────────────────────────────────

app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/todo-flow", api_todo_flow),
        Route("/api/reset", api_reset, methods=["POST"]),
        Route("/api/files", api_files),
        Route("/api/file-content", api_file_content),
        Route("/api/structure/save", api_structure_save, methods=["POST"]),
        Route("/api/structure/export", api_structure_export, methods=["POST"]),
        Route("/api/structure/build-surface", api_structure_build_surface, methods=["POST"]),
        Route("/api/structure/build-surface/", api_structure_build_surface, methods=["POST"]),
        Route("/api/structure/build_surface", api_structure_build_surface, methods=["POST"]),
        Route("/api/structure/build-supercell", api_structure_build_supercell, methods=["POST"]),
        Route("/api/structure/build-supercell/", api_structure_build_supercell, methods=["POST"]),
        Route("/api/structure/build_supercell", api_structure_build_supercell, methods=["POST"]),
        Route("/api/structure/add-molecule", api_structure_add_molecule, methods=["POST"]),
        Route("/api/structure/build-interfaces", api_structure_build_interfaces, methods=["POST"]),
        Route("/api/structure/build-interfaces/save", api_structure_build_interfaces_save, methods=["POST"]),
        Route("/api/structure", api_structure, methods=["GET"]),
        Route("/api/file/delete", api_file_delete, methods=["POST"]),
        Route("/api/file/delete-many", api_file_delete_many, methods=["POST"]),
        Route("/api/file/rename", api_file_rename, methods=["POST"]),
        Route("/api/file/duplicate", api_file_duplicate, methods=["POST"]),
        Route("/api/file/paste", api_file_paste, methods=["POST"]),
        Route("/api/file/upload", api_file_upload, methods=["POST"]),
            Route("/api/sessions", api_sessions_list, methods=["GET"]),
            Route("/api/sessions/rename", api_session_rename, methods=["PATCH"]),
            Route("/api/sessions/delete", api_session_delete, methods=["DELETE"]),
        WebSocketRoute("/ws", ws_chat),
        Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(NoCacheJSMiddleware),
    ],
)


def run_server(host: str = "0.0.0.0", port: int = 8000):
    print(f"\n  AtomSculptor Web GUI  →  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")
