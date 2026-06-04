# The Aggregator reads session notes and condenses them into reusable Skills.
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.skills import (
    create_skill,
    delete_skill,
    list_skills,
    read_skill,
    update_skill,
)
from agent_team.tools.memory_tools import (
    cleanup_marked_notes,
    list_all_note_files,
    read_note_file,
)
from settings import settings


agent_description = (
    "Aggregator Agent that condenses execution notes into reusable Skills "
    "(Anthropic-style: SKILL.md + optional scripts/references)."
)
agent_instruction = """
You are an Aggregator Agent. Your goal is NOT to summarize notes, but to distill
them into reusable **Skills** that future agents will discover via `list_skills`.

A skill is a folder with a `SKILL.md` (YAML frontmatter + body) and optional
`scripts/`, `references/`, `requirements.txt`. Instruction-only skills omit the
`entry` field; runnable skills include `entry: scripts/<file>.py`.

Required workflow:

1. Call `list_all_note_files` and `read_note_file` to load every relevant note.
2. Call `list_skills` to see what already exists. Read each candidate skill's
   SKILL.md with `read_skill(name)` BEFORE deciding to update or replace it.
3. For each note cluster, decide:
   A. Matches an existing skill              -> `update_skill(name, ...)`
   B. Partially overlaps several skills      -> `update_skill` to merge them
   C. Truly new category                     -> `create_skill(...)`
4. Each SKILL.md body must contain:
   - Common Workflow (step-by-step)
   - Key Considerations
   - Common Pitfalls and Fixes
   - Additional Tips
   Be concise and information-dense. Move long worked examples or
   material-specific deep-dives into `references/<topic>.md` for progressive
   disclosure.
5. After the skills are written, call `cleanup_marked_notes` to delete the
   notes you've already aggregated.

Constraints:
- Avoid creating duplicate or near-duplicate skills. Prefer updating/merging.
- Skill names: lowercase, hyphen-separated (e.g. `surface-creation`).
- `description` and `when_to_use` must be one short line each — agents use
  them to decide whether to read the full SKILL.md.
"""


aggregator = Agent(
    model=LiteLlm(settings.AGGREGATOR_MODEL),
    name="aggregator",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        list_all_note_files,
        read_note_file,
        list_skills,
        read_skill,
        create_skill,
        update_skill,
        delete_skill,
        cleanup_marked_notes,
    ],
    output_key="last_aggregator_result",
)
