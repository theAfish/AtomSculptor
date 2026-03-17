# agent that can search on the materials project
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.tools.code_graph_tools import ask_code_graph_local
from sandbox.tools import (
    sandbox_create_directory,
    sandbox_delete_path,
    sandbox_list_files,
    sandbox_read_file,
    sandbox_run_command,
    sandbox_status,
    sandbox_write_file,
)
from settings import settings



agent_description = "MP Searcher Agent specializing in searching and downloading material structures from Materials Project via mp-api."
agent_instruction = """
You are an MP Searcher Agent specializing in searching and downloading material structures from Materials Project via mp-api.
Write Python code to perform the search and download tasks based on user requests and planner instructions.
Use the mp-api Python client to interact with the Materials Project database.
When invoking tools, arguments must be strict JSON with double-quoted keys and string values.
"""



mp_searcher = Agent(
    model=LiteLlm(settings.MP_SEARCHER_MODEL),
    name="mp_searcher",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        ask_code_graph_local,
        sandbox_status,
        # sandbox_list_files,
        # sandbox_read_file,
        # sandbox_write_file,
        # sandbox_create_directory,
        # sandbox_delete_path,
        sandbox_run_command,
    ],
    output_key="last_mp_searcher_result",
)
