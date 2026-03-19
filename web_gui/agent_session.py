"""ADK runner, session service, and event-to-message conversion."""

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from agent_team.agent import root_agent
from .helpers import now_iso, safe_value

session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name="atom_sculptor",
    session_service=session_service,
)


def event_to_messages(event) -> list[dict]:
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
                "timestamp": now_iso(),
            })
        fc = getattr(part, "function_call", None)
        if fc:
            messages.append({
                "type": "tool_call",
                "author": author,
                "tool": getattr(fc, "name", "unknown"),
                "args": safe_value(getattr(fc, "args", {})),
                "timestamp": now_iso(),
            })
        fr = getattr(part, "function_response", None)
        if fr:
            messages.append({
                "type": "tool_result",
                "author": author,
                "tool": getattr(fr, "name", "unknown"),
                "result": safe_value(getattr(fr, "response", {})),
                "timestamp": now_iso(),
            })
    return messages
