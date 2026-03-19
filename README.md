# AtomSculptor

Materials-science agent workspace using Google ADK + Anthropic Sandbox Runtime (`srt`).

## Requirements

- Linux (current project environment)
- Python 3.10+
- Node.js + npm
- `srt` Linux dependencies:
  - `bubblewrap`
  - `socat`
  - `ripgrep`

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y bubblewrap socat ripgrep
```

---

## 1) Create Python environment

```bash
cd AtomSculptor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you use a different model backend, also install any provider SDK required by your LiteLLM model setup.

---

## 2) Install sandbox runtime CLI (`srt`)

```bash
npm install -g @anthropic-ai/sandbox-runtime
srt --help
```

---

## 3) Configure project

Edit `config.yaml`:

```yaml
PLANNER_MODEL: "openai/qwen3-max"
SANDBOX_DIR: "sandbox/runtime"
```

You can also override with env vars:

```bash
export PLANNER_MODEL="openai/qwen3-max"
export SANDBOX_DIR="sandbox/runtime"
```

Set your provider credentials as needed (example):

```bash
export OPENAI_API_KEY="<your_key>"
```

---

## 4) Run the agent

From repo root:

```bash
adk run agent_team
```

If this command fails, verify:

1. Virtual env is active.
2. `google-adk` is installed in that env.
3. Model/API credentials are set.
4. `srt` is installed and Linux deps are present.

---

## Sandbox usage in code

The project exposes a Python wrapper around `srt` in `sandbox/core.py`.

Basic pattern:

```python
from sandbox import Sandbox

sandbox = Sandbox("sandbox/runtime")
sandbox.add_agent(agent)              # or sandbox.add_agent([agent1, agent2])
result = sandbox.run("echo hello")
print(result.stdout)
```

What it does:

- Creates sandbox workspace folder at `sandbox/runtime`
- Stores internal sandbox control files under `sandbox/.sandbox_control/`
  - `sandbox/.sandbox_control/srt-settings.json`
  - `sandbox/.sandbox_control/agents/<agent_name>/`
- Runs commands through:
  - `srt --settings <sandbox_settings_path> <command>`

---

## Code-Graph-RAG Integration

AtomSculptor now includes integrated code analysis capabilities using graph-based RAG (Retrieval-Augmented Generation).

### Quick Setup

1. **Install with all dependencies**:
   ```bash
   ./install.sh
   ```
   Or manually:
   ```bash
   pip install -e .
   pip install -e ".[treesitter-full]"  # Optional: full language support
   ```

2. **Start Memgraph** (required for code analysis):
   ```bash
   docker run -d -p 7687:7687 -p 7444:7444 -p 3000:3000 \
     memgraph/memgraph-platform
   ```

3. **Configure API keys** in `.env` (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

### New Code Analyzer Agent

The `code_analyzer` agent is now available alongside `structure_builder` and `mp_searcher`:

```python
# Ask the planner to analyze code
"Analyze the structure of the agent_team module"

# Find specific functions
"Find the code for the create_plan function"

# Analyze dependencies
"What modules does the planner agent import?"

# Search for patterns
"Search for all classes that inherit from Agent"
```

For detailed documentation, see [CODE_GRAPH_INTEGRATION.md](CODE_GRAPH_INTEGRATION.md).

---

## Useful files

- `agent_team/agent.py` — root ADK agent wiring
- `agent_team/agents/planner.py` — planner definition + tools
- `sandbox/core.py` — `Sandbox` class
- `sandbox/tools.py` — file tools used by planner
- `settings.py` — loads config/env settings
- `config.yaml` — default runtime config

---

## Quick sanity checks

```bash
python -c "from sandbox import Sandbox; s=Sandbox('sandbox/runtime'); print(s.list_agents())"
srt --version
```
