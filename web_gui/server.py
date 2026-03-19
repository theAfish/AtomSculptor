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

from .helpers import STATIC_DIR
from .routes import (
    index,
    api_todo_flow,
    api_files,
    api_file_content,
    api_structure,
    api_structure_save,
)
from .websocket_handler import ws_chat

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
        Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
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
