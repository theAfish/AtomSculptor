from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agent_team.skills import (
    create_skill,
    install_skill_deps,
    list_skills,
    promote_skill,
    read_skill,
    run_skill,
)
from agent_team.tools.code_graph_tools import ask_code_graph_local
from agent_team.tools.planning_tools import (
    complete_task,
    get_plan_summary,
    is_plan_finished,
    start_task,
)
from sandbox.tools import sandbox_run_command
from settings import settings


agent_description = "Structure Builder Agent specializing in atomic simulations and structure manipulations."
agent_instruction = """
You are an expert in atomic modelling using Python, ASE, RDKit, and Pymatgen.
You build and manipulate atomic structures based on user requests and planner
instructions (surfaces, interfaces, supercells, defects, nanostructures, ...).

## Skills are your toolbox

Domain capabilities are packaged as **skills** — self-contained folders with a
`SKILL.md` (frontmatter + instructions), optional `scripts/` (runnable),
`references/` (deeper docs loaded on demand), and `requirements.txt`.

Required workflow:

1. Call `list_skills` first. Read each entry's `description` and `when_to_use`
   to decide which skills apply.
2. Call `read_skill(name)` to load the SKILL.md before acting.
3. For *progressive disclosure*, only after reading SKILL.md, call
   `read_skill(name, "references/<file>.md")` (or `scripts/<file>.py`) to pull
   in extra detail you actually need. Do not load every reference up front.
4. For runnable skills, call `run_skill(name, args)`. Dependencies declared
   in the skill's `requirements.txt` are installed automatically on first use.
   You can also call `install_skill_deps(name)` explicitly.
5. If a needed capability does not exist as a skill, create one with
   `create_skill` (supply `name`, `description`, `when_to_use`, optional
   `entry`, `scripts`, `references`, `requirements`). Once it has proven
   useful, call `promote_skill(name)` to ship it in the built-in library.

## General coding

Use `sandbox_run_command` for ad-hoc code or file operations inside the runtime
sandbox. Ask the code graph (`ask_code_graph_local`) when you need usage
examples for PyMatgen, ASE, RDKit, etc., or when debugging.

Save structures in only one format (default `.extxyz` or `.xyz`); do not
render or visualize unless directly required.
"""


structure_builder = Agent(
    model=LiteLlm(settings.STRUCTURE_BUILDER_MODEL),
    name="structure_builder",
    description=agent_description,
    instruction=agent_instruction,
    tools=[
        # Skill system
        list_skills,
        read_skill,
        run_skill,
        install_skill_deps,
        create_skill,
        promote_skill,
        # General coding / sandbox
        ask_code_graph_local,
        sandbox_run_command,
        # Planning
        get_plan_summary,
        start_task,
        complete_task,
        is_plan_finished,
    ],
    output_key="last_structure_builder_result",
)
