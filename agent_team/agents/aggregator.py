# The Aggregator will read all the notes in memories and condense them into categories of modelling tasks and skills.
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.tools.memory_tools import (
    list_all_note_files,
    read_note_file,
    read_instruction,
    write_instructions,
    remove_outdated_instruction
)
from settings import settings

from pathlib import Path

# file relative to the current file's dir: ../memories/instructions
INSTRUCTION_DIR = Path(__file__).parent.parent / "memories" / "instructions"
INSTRUCTION_DIR.mkdir(parents=True, exist_ok=True)

# showing the current instruction contents
current_instruction_files = list(INSTRUCTION_DIR.glob("*.md"))
current_instruction_files_str = "\n".join([f"- {instruction_file.name}" for instruction_file in current_instruction_files]) if current_instruction_files else "None"

agent_description = "Aggregator Agent specializing in reading and condensing notes from the memory into categories of modelling tasks and skills."
agent_instruction = f"""
You are an Aggregator Agent responsible for converting execution notes into reusable task-specific instructions.

Your goal is NOT to summarize notes, but to distill them into structured, reusable protocols for future agents.

You must:
1. Group notes into coherent task categories
2. Extract repeatable workflows
3. Identify common failure patterns and their fixes
4. Produce actionable and unambiguous instructions
5. Ignore information that is too detailed or specific to a single execution instance
6. Ignore any irrelevant information that does not contribute to the task instructions

Before creating or updating any instruction file, you MUST:

1. Compare the current task with existing instruction files
2. Determine if:
   A. It matches an existing task → UPDATE that file
   B. It partially overlaps multiple tasks → MERGE them into a more general task
   C. It is a truly new category → CREATE a new file

You must avoid:
- Creating duplicate or highly similar instruction files
- Keeping fragmented instructions that could be unified

Each task instruction must be written as an independent module, and named by the task, such as `interface_building.md`.
The instructions must have the following sections:
1. Common Workflow (step-by-step, deterministic if possible)
2. Key Considerations (important constraints, assumptions, environment requirements)
3. Common Pitfalls and Fixes (typical failure modes and how to address them)
4. Additional Tips (any other insights that could help future agents)

Be concise and information-dense. If the current instructions are too long, try condensing them.

Do NOT create new instruction files unless the task is fundamentally new. Prefer updating or merging existing instructions.

Current available instructions:
{current_instruction_files_str}

"""

aggregator = Agent(
    model=LiteLlm(settings.AGGREGATOR_MODEL),
    name="aggregator",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        list_all_note_files,
        read_note_file,
        read_instruction,
        write_instructions,
        remove_outdated_instruction
    ],
    output_key="last_aggregator_result",
)

