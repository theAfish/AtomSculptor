# writing temp memories for planner

import difflib
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

# Resolve from this file location so behavior is stable regardless of cwd.
memory_path = Path(__file__).resolve().parents[1] / "memories" 
notes_path = memory_path / "notes"
instructions_path = memory_path / "instructions"


def _resolve_note_file(file_name: str) -> Path | None:
    """Resolve file_name to a note file path under notes_path only."""
    if not file_name or not file_name.strip():
        return None

    candidate = Path(file_name.strip())
    if not candidate.is_absolute():
        candidate = notes_path / candidate

    try:
        resolved = candidate.resolve()
        resolved.relative_to(notes_path.resolve())
    except (ValueError, OSError):
        return None

    return resolved


def _format_task_report(
    task_type: str,
    success: bool,
    plan: str | None,
    errors_summary: str,
    fix: str,
    useful_info: str,
) -> str:
    """Build a consistent markdown report for planner notes."""
    plan_text = plan.strip() if plan and plan.strip() else "N/A"
    errors_text = errors_summary.strip() if errors_summary and errors_summary.strip() else "None"
    fix_text = fix.strip() if fix and fix.strip() else "None"
    useful_info_text = useful_info.strip() if useful_info and useful_info.strip() else "None"

    status = "SUCCESS" if success else "FAILURE"
    return (
        f"## Task Report: {task_type.strip()}\n"
        f"- Status: {status}\n"
        f"- Plan: {plan_text}\n"
        f"- Errors Summary: {errors_text}\n"
        f"- Fix: {fix_text}\n"
        f"- Useful Info: {useful_info_text}\n"
    )


def write_notes(
    task_type: str,
    success: bool,
    plan: str | None,
    errors_summary: str,
    fix: str,
    useful_info: str,
    tool_context: ToolContext,
) -> dict:
    """Append a structured task report to the current session note file."""
    if not task_type or not task_type.strip():
        return {"error": "task_type must be a non-empty string"}

    notes_path.mkdir(parents=True, exist_ok=True)

    session_id = tool_context.session.id
    note_file = notes_path / f"note_{session_id}.md"
    note_contents = _format_task_report(task_type, success, plan, errors_summary, fix, useful_info)

    with note_file.open("a", encoding="utf-8") as f:
        f.write(note_contents.rstrip() + "\n")

    # change the state to indicate a note has been written
    tool_context.session.state['note_written'] = 'true'
    return {"message": "Note written."}


def rewrite_notes(
    task_type: str,
    success: bool,
    plan: str | None,
    errors_summary: str,
    fix: str,
    useful_info: str,
    tool_context: ToolContext,
) -> dict:
    """Rewrite the session note file with one structured task report."""
    if not task_type or not task_type.strip():
        return {"error": "task_type must be a non-empty string"}

    notes_path.mkdir(parents=True, exist_ok=True)

    session_id = tool_context.session.id
    note_file = notes_path / f"note_{session_id}.md"
    note_contents = _format_task_report(task_type, success, plan, errors_summary, fix, useful_info)

    with note_file.open("w", encoding="utf-8") as f:
        f.write(note_contents.rstrip() + "\n")

    # change the state to indicate a note has been written
    tool_context.session.state['note_written'] = 'true'
    return {"message": "Note rewritten."}


### For the aggregation agent to read back notes and reflect on them
def list_all_note_files(tool_context: ToolContext) -> dict:
    """List all note files in the memory path."""
    notes_path.mkdir(parents=True, exist_ok=True)
    note_files = list(notes_path.glob("note_*.md"))
    return {"note_files": [str(note_file) for note_file in note_files]}

def read_note_file(file_name: str, tool_context: ToolContext) -> dict:
    """Read the contents of a specific note file."""
    notes_path.mkdir(parents=True, exist_ok=True)
    note_file = _resolve_note_file(file_name)
    if note_file is None:
        return {"error": f"Invalid note file path: {file_name}"}

    if not note_file.exists() or not note_file.is_file():
        return {"error": f"Note file not found: {file_name}"}
    
    with note_file.open("r", encoding="utf-8") as f:
        content = f.read()

    # mark the notes read for later cleanup
    note_name = note_file.name
    marked_notes = tool_context.session.state.get("marked_read_notes", [])
    if not isinstance(marked_notes, list):
        marked_notes = [str(marked_notes)]

    if note_name not in marked_notes:
        marked_notes.append(note_name)
        tool_context.session.state["marked_read_notes"] = marked_notes
    
    return {"content": content}


def _delete_marked_notes(tool_context: ToolContext) -> dict:
    """Delete notes previously marked as read in this session."""
    notes_path.mkdir(parents=True, exist_ok=True)

    marked_notes = tool_context.session.state.get("marked_read_notes", [])
    if not isinstance(marked_notes, list):
        marked_notes = [str(marked_notes)]

    if not marked_notes:
        return {
            "message": "No marked notes to delete.",
            "deleted": [],
            "missing": [],
            "failed": [],
            "deleted_count": 0,
        }

    deleted: list[str] = []
    missing: list[str] = []
    failed: list[dict] = []

    for file_name in marked_notes:
        note_file = _resolve_note_file(file_name)
        if note_file is None:
            failed.append({"file": file_name, "error": "Invalid note file path"})
            continue

        if not note_file.exists() or not note_file.is_file():
            missing.append(note_file.name)
            continue

        try:
            note_file.unlink()
            deleted.append(note_file.name)
        except OSError as e:
            failed.append({"file": note_file.name, "error": str(e)})

    tool_context.session.state["marked_read_notes"] = []
    tool_context.session.state["last_deleted_notes"] = deleted

    return {
        "message": "Marked notes cleanup completed.",
        "deleted": deleted,
        "missing": missing,
        "failed": failed,
        "deleted_count": len(deleted),
    }


def read_instruction(instruction_file: str, tool_context: ToolContext) -> dict:
    """Read the contents of a specific instruction file."""
    instructions_path.mkdir(parents=True, exist_ok=True)
    candidate = Path(instruction_file.strip())
    if not candidate.is_absolute():
        candidate = instructions_path / candidate

    try:
        resolved = candidate.resolve()
        resolved.relative_to(instructions_path.resolve())
    except (ValueError, OSError):
        return {"error": f"Invalid instruction file path: {instruction_file}"}

    if not resolved.exists() or not resolved.is_file():
        return {"error": f"Instruction file not found: {instruction_file}"}
    
    with resolved.open("r", encoding="utf-8") as f:
        content = f.read()

    return {"content": content}

def write_instructions(instruction_contents: str, instruction_file: str, overwrite: bool, tool_context: ToolContext) -> dict:
    """Write instructions to a file. The notes read will be automatically cleaned up after writing instructions."""
    if not instruction_contents or not instruction_contents.strip():
        return {"error": "instruction_contents must be a non-empty string"}

    instructions_path.mkdir(parents=True, exist_ok=True)

    instruction_file_path = instructions_path / instruction_file

    if instruction_file_path.exists() and not overwrite:
        return {"error": f"Instruction file already exists: {instruction_file}"}

    with instruction_file_path.open("w", encoding="utf-8") as f:
        f.write(instruction_contents.rstrip() + "\n")

    cleanup_result = _delete_marked_notes(tool_context)
    return {
        "message": "Instructions written.",
        "cleanup": cleanup_result,
    }

def remove_outdated_instruction(instruction_file: str, tool_context: ToolContext) -> dict:
    """Remove an instruction file that is no longer relevant, or can be included in other instructions."""
    instructions_path.mkdir(parents=True, exist_ok=True)
    candidate = Path(instruction_file.strip())
    if not candidate.is_absolute():
        candidate = instructions_path / candidate

    try:
        resolved = candidate.resolve()
        resolved.relative_to(instructions_path.resolve())
    except (ValueError, OSError):
        return {"error": f"Invalid instruction file path: {instruction_file}"}

    if not resolved.exists() or not resolved.is_file():
        return {"error": f"Instruction file not found: {instruction_file}"}

    try:
        resolved.unlink()
        return {"message": f"Instruction file '{instruction_file}' removed."}
    except OSError as e:
        return {"error": f"Failed to remove instruction file: {str(e)}"}
    