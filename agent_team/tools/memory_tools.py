# writing temp memories for planner

import difflib
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

# Resolve from this file location so behavior is stable regardless of cwd.
memory_path = Path(__file__).resolve().parents[1] / "memories" 
notes_path = memory_path / "notes"
instructions_path = memory_path / "instructions"


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
    note_file = notes_path / file_name
    if not note_file.exists() or not note_file.is_file():
        return {"error": f"Note file not found: {file_name}"}
    
    with note_file.open("r", encoding="utf-8") as f:
        content = f.read()
    
    return {"content": content}


def write_instructions(instruction_contents: str, instruction_file: str, tool_context: ToolContext) -> dict:
    """Write instructions to a file."""
    if not instruction_contents or not instruction_contents.strip():
        return {"error": "instruction_contents must be a non-empty string"}

    instructions_path.mkdir(parents=True, exist_ok=True)

    instruction_file_path = instructions_path / instruction_file

    with instruction_file_path.open("w", encoding="utf-8") as f:
        f.write(instruction_contents.rstrip() + "\n")

    return {"message": "Instructions written."}

def update_instruction(instruction_contents: str, instruction_file: str, diff_mode=True) -> dict:
    """Update instructions in a file. If diff_mode is True, only write the diff between existing and new contents."""
    if not instruction_contents or not instruction_contents.strip():
        return {"error": "instruction_contents must be a non-empty string"}

    if not instruction_file or not instruction_file.strip():
        return {"error": "instruction_file must be a non-empty string"}

    instructions_path.mkdir(parents=True, exist_ok=True)

    instruction_file_path = instructions_path / instruction_file
    new_contents = instruction_contents.rstrip() + "\n"

    existing_contents = ""
    if instruction_file_path.exists() and instruction_file_path.is_file():
        with instruction_file_path.open("r", encoding="utf-8") as f:
            existing_contents = f.read()

    if diff_mode:
        diff_lines = list(
            difflib.unified_diff(
                existing_contents.splitlines(keepends=True),
                new_contents.splitlines(keepends=True),
                fromfile=f"{instruction_file} (old)",
                tofile=f"{instruction_file} (new)",
            )
        )
        diff_text = "".join(diff_lines)

        if not diff_text:
            return {"message": "No changes detected.", "updated": False}

        with instruction_file_path.open("w", encoding="utf-8") as f:
            f.write(diff_text)

        return {
            "message": "Instruction updated with diff.",
            "updated": True,
            "diff": diff_text,
        }

    if existing_contents == new_contents:
        return {"message": "No changes detected.", "updated": False}

    with instruction_file_path.open("w", encoding="utf-8") as f:
        f.write(new_contents)

    return {"message": "Instruction updated.", "updated": True}
    