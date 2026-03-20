# AtomSculptor

Materials-science agent workspace using Google ADK + Anthropic Sandbox Runtime (`srt`).

## Requirements

- Linux or WSL2 (current project environment)
- Python 3.12+
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

Optional extras

- `pip install -e ".[web]"` for web UI runtime (`uvicorn`, `starlette`). **Recommended!**
- `pip install -e ".[dev]"` for development tooling (`ruff`, `mypy`, `pre-commit`, `pytest`, `pytest-asyncio`).
- `pip install -e ".[treesitter-full]"` for full Tree-sitter language support (JavaScript/TypeScript/Rust/Go/Scala/Java/C++). Used for code graph RAG.

If you use a different model backend, also install any provider SDK required by your LiteLLM model setup.

---

## 2) Install sandbox runtime CLI (`srt`)

Node.js 18+ is required for some frontend dependencies (e.g. `marked`).

```bash
# Install the sandbox runtime CLI globally
npm install -g @anthropic-ai/sandbox-runtime
srt --help

# Install web GUI frontend dependencies (from the repository root)
# This uses the lockfile to ensure reproducible installs.
cd web_gui/static
npm ci
cd -
```

---

## 3) Configure project

Edit `config.yaml`:

```yaml
PLANNER_MODEL: "openai/qwen3-max"
SANDBOX_DIR: "sandbox/.runtime"
```

Set your provider credentials following `.env` (`cp` one from `.env.example`) or your environment variables:

```bash
OPENAI_API_KEY="<your_key>"
OPENAI_API_BASE="<your_base>"
MP_API_KEY="<your_mp_api>"
```

---

## 4) Run the agent

We support GUI and CLI modes.

From repo root:

For GUI mode, run:

```bash
python main.py --web
```

For CLI mode, run:

```bash
adk run agent_team
```

---

## Code-Graph-RAG Integration

AtomSculptor now includes integrated code analysis capabilities using code-graph-rag.

If using, you need to create a folder that contains the codes like pymatgen, ase, rdkit, etc. and set the path in `TARGET_REPO_PATH` in `config.yaml`. The code analyzer agent will use this path to analyze the code and build the code graph in Memgraph.

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

  Note: `./install.sh` supports non-interactive/CI mode. Set `CI=true` or `NONINTERACTIVE=true` to skip prompts.

2. **Start Memgraph** (required for code analysis):
  ```bash
  docker pull memgraph/memgraph-platform
  ```

  Run the container as you prefer. Example:
  ```bash
  docker run -d --name memgraph -p 7687:7687 memgraph/memgraph-platform
  ```
