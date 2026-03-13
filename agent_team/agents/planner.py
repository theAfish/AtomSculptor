from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm


from sandbox.tools import (
    sandbox_status,
)
from agent_team.tools.state_management_tools import (
    change_state,
)
from agent_team.tools.planning_tools import (
    reset_plan,
    create_plan,
    revise_plan,
    get_plan_summary,
    start_task,
    complete_task,
    is_plan_finished
)
from agent_team.tools.memory_tools import (
    write_notes,
)
from settings import settings
from agent_team.agents.structure_builder import structure_builder
from agent_team.agents.mp_searcher import mp_searcher


agent_description = "Planner that manages a specialized team of agents for materials science and code analysis tasks."
agent_instruction = """
You are the Planner orchestrating a specialized team for materials science research and code analysis. You have three specialist sub-agents available:
- **structure_builder**: For building and manipulating atomic structures using ASE
- **mp_searcher**: For searching and downloading materials from Materials Project

**Decision Making:**
1. For simple queries or general conversation: Respond directly WITHOUT changing workflow state.
2. For tasks requiring sub-agents:
   - Properly set the session state
   - Propose plans using `create_plan` and `revise_plan` tools
   - Construct and update plans iteratively based on results and feedback
   - Dynamically delegate to sub-agents as needed, using the `current_stage` state to manage workflow
   - Finish all the tasks indicate the user's request is complete
3. After delegating work:
   - Review the results
   - Use `change_state(state_name="to_human", state_value="true")` to return results to user
   - Or continue with more work if needed
4. Write notes for future agents. Record important observations such as successful strategies for this type of task, pitfalls encountered, approaches that should be avoided, etc.

**State Management:**
- Use `change_state(state_name="current_stage", state_value="modelling")` to signal the orchestrator that modelling work is in progress
- Only do this if you're delegating to sub-agents and want the full modelling workflow
- For simple sub-agent calls during planning, you don't need to change the stage
"""



planner = Agent(
    model=LiteLlm(settings.PLANNER_MODEL),
    name="planner",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        sandbox_status,
        change_state,
        reset_plan,
        create_plan,
        revise_plan,
        get_plan_summary,
        start_task,
        complete_task,
        is_plan_finished,
        write_notes,
    ],
    sub_agents=[structure_builder, mp_searcher],
    output_key="last_planner_result",
)
