"""WebSocket handler for real-time chat, agent events, and live updates."""

import asyncio
import traceback

from google.genai import types
from starlette.websockets import WebSocket, WebSocketDisconnect

from agent_team.agents.atom_sculptor import get_aggregator_status

from .agent_session import runner, session_service, event_to_messages
from .filesystem import sandbox_root, build_file_tree
from .helpers import now_iso
from .todo import serialize_todo_flow


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


async def _close_quietly(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except (RuntimeError, WebSocketDisconnect):
        pass


async def _push_aggregator_status(websocket: WebSocket) -> None:
    last_sent: dict | None = None
    while True:
        status = get_aggregator_status()
        if status != last_sent:
            if not await _send_json_or_stop(
                websocket, {"type": "aggregator_status", "data": status},
            ):
                return
            last_sent = status
        await asyncio.sleep(0.75)


async def _push_file_updates(websocket: WebSocket) -> None:
    """Poll and push file tree updates when changes are detected."""
    import json
    last_sent: str | None = None
    while True:
        try:
            root = sandbox_root()
            current_tree = build_file_tree(root, root)
            # Use JSON serialization as a simple way to detect changes
            current_json = json.dumps(current_tree, sort_keys=True, default=str)
            if current_json != last_sent:
                if not await _send_json_or_stop(
                    websocket, {"type": "files_update", "data": current_tree},
                ):
                    return
                last_sent = current_json
        except Exception:
            # Silently ignore errors and continue polling
            pass
        await asyncio.sleep(0.5)


async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    user_id = "web_user"
    status_task: asyncio.Task | None = None
    file_task: asyncio.Task | None = None

    # Create ADK session
    try:
        session = await session_service.create_session(
            app_name="atom_sculptor", user_id=user_id,
        )
        session_id = getattr(session, "id", None) or getattr(
            session, "session_id", f"ws_{id(websocket)}"
        )
    except Exception as exc:
        if await _send_json_or_stop(
            websocket, {"type": "error", "text": f"Session error: {exc}"}
        ):
            await _close_quietly(websocket)
        return

    # Push initial state
    root = sandbox_root()
    if not await _send_json_or_stop(
        websocket, {"type": "todo_flow_update", "data": serialize_todo_flow()}
    ):
        return
    if not await _send_json_or_stop(
        websocket, {"type": "files_update", "data": build_file_tree(root, root)},
    ):
        return

    status_task = asyncio.create_task(_push_aggregator_status(websocket))
    file_task = asyncio.create_task(_push_file_updates(websocket))

    try:
        while True:
            raw = await websocket.receive_json()
            kind = raw.get("type")

            if kind == "chat":
                user_text = raw.get("message", "").strip()
                if not user_text:
                    continue

                if not await _send_json_or_stop(
                    websocket,
                    {"type": "user_message", "text": user_text, "timestamp": now_iso()},
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
                        for msg in event_to_messages(event):
                            if not await _send_json_or_stop(websocket, msg):
                                return
                        if not await _send_json_or_stop(
                            websocket,
                            {"type": "todo_flow_update", "data": serialize_todo_flow()},
                        ):
                            return

                    if not await _send_json_or_stop(websocket, {"type": "done"}):
                        return
                    root = sandbox_root()
                    if not await _send_json_or_stop(
                        websocket,
                        {"type": "files_update", "data": build_file_tree(root, root)},
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
                root = sandbox_root()
                if not await _send_json_or_stop(
                    websocket,
                    {"type": "files_update", "data": build_file_tree(root, root)},
                ):
                    return

            elif kind == "refresh_todo":
                if not await _send_json_or_stop(
                    websocket,
                    {"type": "todo_flow_update", "data": serialize_todo_flow()},
                ):
                    return

    except WebSocketDisconnect:
        pass
    finally:
        if status_task is not None:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass
        if file_task is not None:
            file_task.cancel()
            try:
                await file_task
            except asyncio.CancelledError:
                pass
