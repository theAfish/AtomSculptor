#!/usr/bin/env bash
# One-step installation script for AtomSculptor
#
# Usage:
#   ./install.sh              # default: core + web extras
#   ./install.sh --all        # core + web + treesitter-full + dev
#   ./install.sh --dev        # core + web + dev extras
#   ./install.sh --no-venv    # skip venv creation (use current environment)

set -euo pipefail

INSTALL_ALL=false
INSTALL_DEV=false
SKIP_VENV=false

require_sudo() {
    if command -v sudo > /dev/null 2>&1; then
        echo "sudo"
        return 0
    fi

    if [ "$(id -u)" -eq 0 ]; then
        echo ""
        return 0
    fi

    echo "ERROR: Need root privileges to install system dependencies. Re-run as root or install sudo." >&2
    exit 1
}

install_linux_system_deps() {
    local missing_packages=()
    local sudo_cmd=""

    command -v bwrap > /dev/null 2>&1 || missing_packages+=("bubblewrap")
    command -v socat > /dev/null 2>&1 || missing_packages+=("socat")
    command -v rg > /dev/null 2>&1 || missing_packages+=("ripgrep")

    if [ "${#missing_packages[@]}" -eq 0 ]; then
        echo "  ✓ System packages already available"
        return 0
    fi

    if ! command -v apt-get > /dev/null 2>&1; then
        echo "  ⚠  Missing system packages: ${missing_packages[*]}"
        echo "     Automatic installation is currently supported only on Debian/Ubuntu (apt-get)."
        return 0
    fi

    sudo_cmd="$(require_sudo)"
    echo "  Installing missing packages: ${missing_packages[*]}"
    $sudo_cmd apt-get update
    $sudo_cmd apt-get install -y "${missing_packages[@]}"
    echo "  ✓ System packages installed"
}

ensure_srt_on_path() {
    local npm_prefix=""
    local npm_bin_dir=""

    if command -v srt > /dev/null 2>&1; then
        return 0
    fi

    if ! command -v npm > /dev/null 2>&1; then
        return 1
    fi

    npm_prefix="$(npm prefix -g 2>/dev/null || true)"
    npm_bin_dir="$npm_prefix/bin"
    if [ -n "$npm_prefix" ] && [ -x "$npm_bin_dir/srt" ]; then
        export PATH="$npm_bin_dir:$PATH"
        return 0
    fi

    return 1
}

install_sandbox_runtime() {
    local sudo_cmd=""

    if ensure_srt_on_path; then
        echo "  ✓ sandbox runtime CLI already installed"
        return 0
    fi

    if ! command -v npm > /dev/null 2>&1; then
        echo "ERROR: npm is required to install @anthropic-ai/sandbox-runtime automatically." >&2
        echo "Install Node.js 18+ and rerun ./install.sh." >&2
        exit 1
    fi

    echo "  Installing @anthropic-ai/sandbox-runtime..."
    if ! npm install -g @anthropic-ai/sandbox-runtime; then
        sudo_cmd="$(require_sudo)"
        $sudo_cmd npm install -g @anthropic-ai/sandbox-runtime
    fi

    if ! ensure_srt_on_path; then
        echo "ERROR: sandbox runtime CLI installed, but 'srt' is not on PATH." >&2
        echo "Add '$(npm prefix -g)/bin' to PATH and rerun." >&2
        exit 1
    fi

    echo "  ✓ sandbox runtime CLI installed"
}

for arg in "$@"; do
    case "$arg" in
        --all)      INSTALL_ALL=true ;;
        --dev)      INSTALL_DEV=true ;;
        --no-venv)  SKIP_VENV=true ;;
        -h|--help)
            echo "Usage: ./install.sh [--all] [--dev] [--no-venv]"
            echo "  --all      Install all optional extras (web, dev, treesitter-full)"
            echo "  --dev      Include development dependencies"
            echo "  --no-venv  Skip virtual environment creation"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg (try --help)"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  AtomSculptor Installation"
echo "=========================================="

# ── 1. Check Python ──────────────────────────────────────────────────────────
echo ""
echo "[1/6] Checking Python..."
if ! command -v python3 > /dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi
PYTHON_BIN=$(command -v python3)
PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python >= $REQUIRED_VERSION required (found $PYTHON_VERSION)"
    exit 1
fi
echo "  ✓ Python $PYTHON_VERSION"

# ── 2. System dependencies ───────────────────────────────────────────────────
echo ""
echo "[2/6] Installing sandbox runtime dependencies..."
install_linux_system_deps

# ── 3. Virtual environment ───────────────────────────────────────────────────
echo ""
echo "[3/6] Setting up virtual environment..."
if [ "$SKIP_VENV" = true ]; then
    echo "  Skipped (--no-venv)"
    PIP_BIN="$PYTHON_BIN -m pip"
else
    if [ ! -d .venv ]; then
        "$PYTHON_BIN" -m venv .venv
        echo "  ✓ Created .venv"
    else
        echo "  ✓ .venv already exists"
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    PIP_BIN="pip"
fi

# ── 4. Python dependencies ───────────────────────────────────────────────────
echo ""
echo "[4/6] Installing Python dependencies..."
if [ "$INSTALL_ALL" = true ]; then
    $PIP_BIN install -e ".[web,dev,treesitter-full]"
elif [ "$INSTALL_DEV" = true ]; then
    $PIP_BIN install -e ".[web,dev]"
else
    $PIP_BIN install -e ".[web]"
fi
echo "  ✓ Python packages installed"

# ── 5. Sandbox runtime + frontend dependencies ───────────────────────────────
echo ""
echo "[5/6] Installing sandbox runtime + frontend dependencies..."
install_sandbox_runtime
if command -v npm > /dev/null 2>&1; then
    (cd web_gui/static && npm ci --silent 2>/dev/null || npm install --silent)
    echo "  ✓ npm packages installed"
else
    echo "  ⚠  npm not found – skipping frontend install"
    echo "     Install Node.js 18+ and run: cd web_gui/static && npm ci"
fi

# ── 6. Environment file ──────────────────────────────────────────────────────
echo ""
echo "[6/6] Checking .env..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "  ✓ Created .env from .env.example"
        echo "  ⚠  Edit .env and add your API keys"
    else
        echo "  ⚠  No .env.example found – create .env manually"
    fi
else
    echo "  ✓ .env already exists"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  ✓ Installation complete!"
echo "=========================================="
echo ""
echo "Quick start:"
if [ "$SKIP_VENV" = false ]; then
    echo "  source .venv/bin/activate"
fi
echo "  python main.py --web          # web GUI on http://localhost:8000"
echo "  python main.py                # ADK CLI mode"
echo "  srt --version                 # verify sandbox runtime CLI"
echo ""
echo "Optional: start Memgraph for code-graph-rag features:"
echo "  docker compose up -d"
echo ""
