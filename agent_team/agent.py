from agent_team.adk_compat import patch_litellm_tool_argument_parsing
from agent_team.agents.planner import planner
from agent_team.agents.structure_builder import structure_builder
from agent_team.agents.mp_searcher import mp_searcher
from agent_team.agents.atom_sculptor import atom_sculptor
from sandbox import Sandbox
from settings import settings


patch_litellm_tool_argument_parsing()

sandbox = Sandbox(settings.SANDBOX_DIR)
sandbox.add_agent([planner, structure_builder, mp_searcher])

root_agent = atom_sculptor
