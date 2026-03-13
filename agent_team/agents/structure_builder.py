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
    sandbox_create_directory,
    sandbox_delete_path,
    sandbox_list_files,
    sandbox_read_file,
    sandbox_run_command,
    sandbox_status,
    sandbox_write_file,
)
from agent_team.tools.planning_tools import (
    complete_task,
    start_task,
    get_plan_summary,
    is_plan_finished,
)
from settings import settings



agent_description = "Structure Builder Agent specializing in atomic simulations and structure manipulations using ASE."
agent_instruction = """
You are an expert in atomic modelling using Python, ASE, RDKit, and Pymatgen. Your ONLY tasks are: 
1. Read and analyze atomic structures from files.
2. Write python scripts to perform structure manipulation and modeling.
3. Build structures according to user specifications.
4. Execute scripts to perform calculations, modeling and return results.
5. Please ensure all generated structures are physically reasonable.
6. Avoid reading structure files in text format unless you know it is short.

For the complex tasks such as interface building, you can use the predefined tools.

You can use the sandbox_run_command in the runtime sandbox when coding or file operations are requested.
Also, you can ask the code graph for usage about packages like PyMatgen, ASE, RDKit, etc. using the ask_code_graph_local tool if needed.

If you are not sure, or get errors while writing codes, ask the code graph for help.

If you need material structures during your work, request them from the MP Searcher or Planner (you are being called by the planner, so communicate any additional needs).

When invoking tools, arguments must be strict JSON with double-quoted keys and string values.
"""



structure_builder = Agent(
    model=LiteLlm(settings.STRUCTURE_BUILDER_MODEL),
    name="structure_builder",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        check_close_atoms,
        read_structure,
        calculate_distance,
        build_supercell,
        build_surface,
        build_interface,
        ask_code_graph_local,
        # sandbox_status,
        # sandbox_list_files,
        # sandbox_read_file,
        # sandbox_write_file,
        # sandbox_create_directory,
        # sandbox_delete_path,
        sandbox_run_command,
        get_plan_summary,
        start_task,
        complete_task,
        is_plan_finished,
    ],
    output_key="last_structure_builder_result",
)
