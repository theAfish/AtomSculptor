# AtomSculptor

Materials-science agent workspace using Google ADK + Anthropic Sandbox Runtime (`srt`).

## Requirements

- Linux or WSL2
- Python 3.12+
- Node.js 18+ / npm
- On Debian/Ubuntu, `./install.sh` will automatically install `bubblewrap`, `socat`, `ripgrep`, and the Anthropic sandbox runtime CLI.

---

## Quick Install

```bash
git clone <repo-url> && cd AtomSculptor
./install.sh
```

This creates a `.venv`, installs Python packages, installs the sandbox runtime CLI (`srt`) and its Linux dependencies when supported, installs frontend dependencies, and sets up `.env`.

Flags:
| Flag | Effect |
|------|--------|
| `--all` | Install all extras (web + dev + treesitter-full) |
| `--dev` | Include development tools (ruff, mypy, pytest, …) |
| `--no-venv` | Skip venv creation; use current environment |

---

## Manual Install

```bash
sudo apt-get install -y bubblewrap socat ripgrep

python3 -m venv .venv && source .venv/bin/activate

# Core + web GUI (recommended)
pip install -e ".[web]"

# Optional extras (combine as needed)
pip install -e ".[dev]"               # ruff, mypy, pytest
pip install -e ".[treesitter-full]"   # JS/TS/Rust/Go/Scala/Java/C++ parsers

# Frontend
cd web_gui/static && npm ci && cd -

# Sandbox runtime CLI
npm install -g @anthropic-ai/sandbox-runtime

# Environment
cp .env.example .env   # then edit with your API keys
```

---

## Configuration

Edit `config.yaml` to set model backends and sandbox paths:

```yaml
PLANNER_MODEL: "openai/qwen3-max"
SANDBOX_DIR: "sandbox/.runtime"
```

Set credentials in `.env`:

```bash
OPENAI_API_KEY="<your_key>"
OPENAI_API_BASE="<your_base>"
MP_API_KEY="<your_mp_api>"
```

---

## Run

```bash
source .venv/bin/activate

# Web GUI (recommended)
python main.py --web

# ADK CLI
python main.py
# or equivalently:
adk run agent_team
```

---

## Code-Graph-RAG Integration

Optional code analysis powered by Memgraph. Requires Docker.

```bash
# Start Memgraph
docker compose up -d

# Or manually:
docker run -d --name memgraph -p 7687:7687 memgraph/memgraph-platform
```

Set `TARGET_REPO_PATH` in `config.yaml` to point at the codebase to analyze (e.g. pymatgen, ase, rdkit sources). Install full tree-sitter support for multi-language parsing:

```bash
pip install -e ".[treesitter-full]"
```
