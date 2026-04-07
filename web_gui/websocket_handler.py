"""WebSocket handler for real-time chat, agent events, and live updates."""

import asyncio
import traceback

from google.genai import types
from starlette.websockets import WebSocket, WebSocketDisconnect

from agent_team.aggregator_runner import get_status as get_aggregator_status

from .agent_session import runner, session_service, event_to_messages
from .file_watcher import file_watcher
from .filesystem import sandbox_root, build_file_tree
from .helpers import now_iso
from .todo import serialize_todo_flow
from . import session_store


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
    """Subscribe to the shared file-tree watcher and push updates to *websocket*.

    The watcher is event-driven (watchdog) and shared across all clients,
    so this coroutine simply blocks on the queue and forwards each snapshot.
    """
    q = file_watcher.subscribe()
    try:
        while True:
            tree = await q.get()
            if not await _send_json_or_stop(websocket, {"type": "files_update", "data": tree}):
                return
    finally:
        file_watcher.unsubscribe(q)


_STORED_MSG_TYPES = {"user_message", "agent_message", "tool_call", "tool_result", "error"}


async def _send_and_store(
    websocket: WebSocket, payload: dict, sid: str
) -> bool:
    """Send *payload* over *websocket* and persist it in the session store."""
    if payload.get("type") in _STORED_MSG_TYPES:
        session_store.add_message(sid, payload)
    return await _send_json_or_stop(websocket, payload)


async def _run_agent_task(
    websocket: WebSocket, user_id: str, session_id: str, user_text: str
) -> None:
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
                if not await _send_and_store(websocket, msg, session_id):
                    return
            if not await _send_json_or_stop(
                websocket,
                {"type": "todo_flow_update", "data": serialize_todo_flow()},
            ):
                return

        if not await _send_json_or_stop(websocket, {"type": "done"}):
            return
        root = sandbox_root()
        await _send_json_or_stop(
            websocket,
            {"type": "files_update", "data": build_file_tree(root, root)},
        )
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        return
    except Exception as exc:
        err_payload = {
            "type": "error",
            "text": str(exc),
            "traceback": traceback.format_exc(),
        }
        session_store.add_message(session_id, err_payload)
        await _send_json_or_stop(websocket, err_payload)


async def _cancel_agent(agent_task: asyncio.Task | None) -> None:
    if agent_task and not agent_task.done():
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


async def _create_adk_session(user_id: str, fallback_id: str) -> str:
    session = await session_service.create_session(
        app_name="atom_sculptor", user_id=user_id,
    )
    return getattr(session, "id", None) or getattr(
        session, "session_id", fallback_id
    )


async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    user_id = "web_user"
    status_task: asyncio.Task | None = None
    file_task: asyncio.Task | None = None
    agent_task: asyncio.Task | None = None

    # Create first ADK session
    try:
        session_id = await _create_adk_session(user_id, f"ws_{id(websocket)}")
    except Exception as exc:
        if await _send_json_or_stop(
            websocket, {"type": "error", "text": f"Session error: {exc}"}
        ):
            await _close_quietly(websocket)
        return

    # Register initial session
    name = session_store._next_name()
    session_store.register(session_id, name)

    # Push initial state
    root = sandbox_root()
    # Ensure the shared file watcher is running (no-op if already started)
    file_watcher.start(asyncio.get_event_loop(), root)
    if not await _send_json_or_stop(
        websocket, {"type": "todo_flow_update", "data": serialize_todo_flow()}
    ):
        return
    if not await _send_json_or_stop(
        websocket, {"type": "files_update", "data": build_file_tree(root, root)},
    ):
        return
    if not await _send_json_or_stop(
        websocket,
        {
            "type": "session_activated",
            "session_id": session_id,
            "name": name,
            "messages": [],
            "sessions": session_store.list_sessions(),
        },
    ):
        return

    status_task = asyncio.create_task(_push_aggregator_status(websocket))
    file_task = asyncio.create_task(_push_file_updates(websocket))

    recv_task: asyncio.Task = asyncio.create_task(websocket.receive_json())
    try:
        while True:
            wait_set = {recv_task}
            if agent_task and not agent_task.done():
                wait_set.add(agent_task)

            done_set, _ = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)

            if agent_task in done_set:
                agent_task = None

            if recv_task not in done_set:
                continue

            try:
                raw = recv_task.result()
            except (WebSocketDisconnect, Exception):
                break
            recv_task = asyncio.create_task(websocket.receive_json())

            kind = raw.get("type")

            if kind == "chat":
                if agent_task and not agent_task.done():
                    continue
                user_text = raw.get("message", "").strip()
                if not user_text:
                    continue
                user_msg = {"type": "user_message", "text": user_text, "timestamp": now_iso()}
                if not await _send_and_store(websocket, user_msg, session_id):
                    break
                agent_task = asyncio.create_task(
                    _run_agent_task(websocket, user_id, session_id, user_text)
                )

            elif kind == "new_session":
                await _cancel_agent(agent_task)
                agent_task = None
                try:
                    new_sid = await _create_adk_session(user_id, f"ws_{id(websocket)}_new")
                    new_name = session_store._next_name()
                    session_store.register(new_sid, new_name)
                    session_id = new_sid
                    if not await _send_json_or_stop(
                        websocket,
                        {
                            "type": "session_activated",
                            "session_id": session_id,
                            "name": new_name,
                            "messages": [],
                            "sessions": session_store.list_sessions(),
                        },
                    ):
                        break
                    if not await _send_json_or_stop(
                        websocket, {"type": "todo_flow_update", "data": serialize_todo_flow()}
                    ):
                        break
                except Exception as exc:
                    await _send_json_or_stop(
                        websocket, {"type": "error", "text": f"New session error: {exc}"}
                    )

            elif kind == "switch_session":
                target_id = raw.get("session_id", "")
                if not target_id or target_id not in {s["id"] for s in session_store.list_sessions()}:
                    await _send_json_or_stop(
                        websocket, {"type": "error", "text": "Session not found"}
                    )
                    continue
                await _cancel_agent(agent_task)
                agent_task = None
                session_id = target_id
                entry_name = next(
                    (s["name"] for s in session_store.list_sessions() if s["id"] == target_id),
                    target_id,
                )
                if not await _send_json_or_stop(
                    websocket,
                    {
                        "type": "session_activated",
                        "session_id": session_id,
                        "name": entry_name,
                        "messages": session_store.get_messages(session_id),
                        "sessions": session_store.list_sessions(),
                    },
                ):
                    break

            elif kind == "stop":
                if agent_task and not agent_task.done():
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    agent_task = None
                await _send_json_or_stop(websocket, {"type": "done"})

            elif kind == "refresh_files":
                root = sandbox_root()
                if not await _send_json_or_stop(
                    websocket,
                    {"type": "files_update", "data": build_file_tree(root, root)},
                ):
                    break

            elif kind == "refresh_todo":
                if not await _send_json_or_stop(
                    websocket,
                    {"type": "todo_flow_update", "data": serialize_todo_flow()},
                ):
                    break

    except WebSocketDisconnect:
        pass
    finally:
        recv_task.cancel()
        if agent_task is not None:
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
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
