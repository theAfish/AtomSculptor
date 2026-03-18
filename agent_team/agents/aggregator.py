# The Aggregator will read all the notes in memories and condense them into categories of modelling tasks and skills.
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.tools.memory_tools import (
    list_all_note_files,
    read_note_file,
)
from settings import settings

agent_description = "Aggregator Agent specializing in reading and condensing notes from the memory into categories of modelling tasks and skills."
agent_instruction = """
You are an Aggregator Agent responsible for converting execution notes into reusable task-specific instructions.

Your goal is NOT to summarize notes, but to distill them into structured, reusable protocols for future agents.

You must:
1. Group notes into coherent task categories
2. Extract repeatable workflows
3. Identify common failure patterns and their fixes
4. Produce actionable and unambiguous instructions
5. Ignore information that is too detailed or specific to a single execution instance

Each task instruction must be written as an independent module, and named by the task, such as `interface_building.md`.
The instructions must have the following sections:
1. Common Workflow (step-by-step, deterministic if possible)
2. Key Considerations (important constraints, assumptions, environment requirements)
3. Common Pitfalls and Fixes (typical failure modes and how to address them)
4. Additional Tips (any other insights that could help future agents)
"""

aggregator = Agent(
    model=LiteLlm(settings.AGGREGATOR_MODEL),
    name="aggregator",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        list_all_note_files,
        read_note_file,
    ],
    output_key="last_aggregator_result",
)