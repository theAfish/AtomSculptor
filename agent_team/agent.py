from agent_team.adk_compat import patch_litellm_tool_argument_parsing
from agent_team.agents.planner import planner
from agent_team.agents.structure_builder import structure_builder
from agent_team.agents.mp_searcher import mp_searcher
from agent_team.agents.atom_sculptor import atom_sculptor
from sandbox import Sandbox
from settings import settings
from pathlib import Path
import shutil

def ensure_toolbox_in_runtime() -> None:
    toolbox_dir = Path(__file__).parent / "toolbox"
    runtime_dir = Path(settings.SANDBOX_DIR)
    dst = runtime_dir / "toolbox"

    runtime_dir.mkdir(parents=True, exist_ok=True)
    if toolbox_dir.exists(): #  and not dst.exists()
        shutil.copytree(toolbox_dir, dst, dirs_exist_ok=True)


patch_litellm_tool_argument_parsing()

sandbox = Sandbox(settings.SANDBOX_DIR)
sandbox.add_agent([planner, structure_builder, mp_searcher])


ensure_toolbox_in_runtime()

root_agent = atom_sculptor
