from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm


from agent_team.tools.code_graph_tools import ask_code_graph_local
from agent_team.tools.structure_tools import (
    check_close_atoms,
    read_structure,
    calculate_distance,
    build_supercell,
    build_surface,
    build_interface
)
from sandbox.tools import (
    sandbox_run_command,
)
from agent_team.tools.planning_tools import (
    complete_task,
    start_task,
    get_plan_summary,
    is_plan_finished,
)
from settings import settings

TOOLBOX_DIR = "toolbox/structure_modelling"



agent_description = "Structure Builder Agent specializing in atomic simulations and structure manipulations."
agent_instruction = f"""
You are an expert in atomic modelling using Python, ASE, RDKit, and Pymatgen. 
Your tasks are to build and manipulate atomic structures based on user requests and planner instructions, such as building surfaces, interfaces, supercells, etc.

Advanced structure building CLI such as interface building are available inside `{TOOLBOX_DIR}` for complex tasks. Inside the sandbox, run them with `python3`, for example `python3 {TOOLBOX_DIR}/structure_tools.py ...`. Check the `doc.md` inside the folder for details.
**Always check the toolbox first before writing codes from scratch.**

You can use the sandbox_run_command in the runtime sandbox when coding or file operations are requested.

Also, you can ask the code graph for usage about packages like PyMatgen, ASE, RDKit, etc. using the ask_code_graph_local tool if needed.

If you are not sure, or get errors while writing codes, ask the code graph for help.
"""



structure_builder = Agent(
    model=LiteLlm(settings.STRUCTURE_BUILDER_MODEL),
    name="structure_builder",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        # check_close_atoms,
        # read_structure,
        # calculate_distance,
        # build_supercell,
        # build_surface,
        # build_interface,
        ask_code_graph_local,
        sandbox_run_command,
        get_plan_summary,
        start_task,
        complete_task,
        is_plan_finished,
    ],
    output_key="last_structure_builder_result",
)
