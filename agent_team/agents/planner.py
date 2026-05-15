from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.agents.mp_searcher import mp_searcher
from agent_team.agents.structure_builder import structure_builder
from agent_team.skills import list_skills, read_skill
from agent_team.tools.ddgs_search_tools import web_search, web_search_news
from agent_team.tools.memory_tools import rewrite_notes, write_notes
from agent_team.tools.planning_tools import (
    complete_task,
    create_plan,
    get_plan_summary,
    is_plan_finished,
    reset_plan,
    revise_plan,
    start_task,
)
from agent_team.tools.state_management_tools import change_state
from sandbox.tools import sandbox_run_command, sandbox_status
from settings import settings


def _format_skill_index() -> str:
    skills = list_skills()["skills"]
    if not skills:
        return "(no skills installed)"
    lines = []
    for entry in skills:
        kind = "runnable" if entry["runnable"] else "instruction"
        lines.append(f"- {entry['name']} ({kind}) — {entry['description']}")
    return "\n".join(lines)


SKILL_INDEX = _format_skill_index()

agent_description = "Planner that manages a specialized team of agents for materials science and code analysis tasks."
agent_instruction = f"""
You are the Planner orchestrating a specialized team for materials science research and code analysis. 

**Decision Making:**
1. For simple queries or general conversation: Respond directly.
2. For tasks requiring sub-agents:
- Properly set the session state
- Propose plans using `create_plan` and `revise_plan` tools
- Decide which **skills** the sub-agents should use (`list_skills` / `read_skill`)
- Construct and update plans iteratively based on results and feedback
- Dynamically delegate to sub-agents as needed, using the `current_stage` state to manage workflow
- Finish all the tasks indicate the user's request is complete
3. After delegating work:
- Review the results
- Use `change_state(state_name="to_human", state_value="true")` to return results to user
- Or continue with more work if needed
4. Write notes for future agents when important experiences or insights are gained.

**State Management:**
- Use `change_state(state_name="current_stage", state_value="modelling")` to signal the orchestrator that modelling work is in progress
- Only do this if you're delegating to sub-agents and want the full modelling workflow
- For simple sub-agent calls during planning, you don't need to change the stage

**Skill index** (sub-agents discover the same skills via `list_skills`):
{SKILL_INDEX}

Use `read_skill(name)` to inspect a skill's SKILL.md before instructing a sub-agent
to apply it.
"""


planner = Agent(
    model=LiteLlm(settings.PLANNER_MODEL),
    name="planner",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        sandbox_status,
        sandbox_run_command,
        change_state,
        reset_plan,
        create_plan,
        revise_plan,
        get_plan_summary,
        start_task,
        complete_task,
        is_plan_finished,
        write_notes,
        rewrite_notes,
        web_search,
        web_search_news,
        list_skills,
        read_skill,
    ],
    sub_agents=[structure_builder, mp_searcher],
    output_key="last_planner_result",
)
