# writing temp memories for planner

from pathlib import Path

from google.adk.tools.tool_context import ToolContext

# Resolve from this file location so behavior is stable regardless of cwd.
memory_path = Path(__file__).resolve().parents[1] / "notes" / "memories"


def write_notes(note_contents: str, tool_context: ToolContext) -> dict:
    """Record note contents. Appends to the current session's note file."""
    if not note_contents or not note_contents.strip():
        return {"error": "note_contents must be a non-empty string"}

    memory_path.mkdir(parents=True, exist_ok=True)

    session_id = tool_context.session.id
    note_file = memory_path / f"note_{session_id}.md"

    with note_file.open("a", encoding="utf-8") as f:
        f.write(note_contents.rstrip() + "\n")

    # change the state to indicate a note has been written
    tool_context.session.state['note_written'] = 'true'
    return {"message": "Note written."}