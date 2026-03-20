#!/usr/bin/env bash
# Installation script for AtomSculptor with code-graph-rag integration

set -euo pipefail

echo "=========================================="
echo "AtomSculptor Installation"
echo "=========================================="

# Check Python version
echo "Checking Python availability and version..."
if ! command -v python3 > /dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi
PYTHON_BIN=$(command -v python3)
PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python $REQUIRED_VERSION or higher is required (found: $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python version OK: $PYTHON_VERSION (using $PYTHON_BIN)"

# Install main dependencies
echo ""
echo "Installing AtomSculptor dependencies..."
"$PYTHON_BIN" -m pip install -e .

# quickly verify that the local code_graph_rag package is importable
python3 - <<'PYCODE'
import sys
try:
    import code_graph_rag
    print("✓ code_graph_rag importable")
except ImportError:
    print("⚠️  code_graph_rag not importable – check pyproject.toml package configuration")
    sys.exit(1)
PYCODE

# Helper to ask yes/no, respects CI/non-interactive environment
ask_yes_no() {
    local prompt="$1"
    if [ "${CI:-}" = "true" ] || [ "${NONINTERACTIVE:-}" = "true" ] || [ "${YES:-}" = "true" ]; then
        return 1  # default to 'no' in CI/non-interactive
    fi
    read -p "$prompt (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

echo ""
if ask_yes_no "Install full tree-sitter language support?"; then
    echo "Installing tree-sitter language parsers..."
    "$PYTHON_BIN" -m pip install -e ".[treesitter-full]"
fi

echo ""
if ask_yes_no "Install development dependencies?"; then
    echo "Installing development dependencies..."
    "$PYTHON_BIN" -m pip install -e ".[dev]"
fi

# Check for .env file
echo ""
if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo "⚠️  .env.example not found; create .env manually"
    else
        echo "Creating .env file from template..."
        cp .env.example .env
        echo "✓ Created .env file"
        echo "⚠️  Please edit .env and add your API keys"
    fi
else
    echo "✓ .env file already exists"
fi

# Check for Docker
echo ""
echo "Checking for Docker..."
    if command -v docker &> /dev/null; then
    echo "✓ Docker is installed"
    
    # Check if Memgraph is running
    if docker ps | grep -q memgraph; then
        echo "✓ Memgraph is already running"
    else
        echo ""
        read -p "Start Memgraph with Docker? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Starting Memgraph..."
            docker run -d --name memgraph \
                -p 7687:7687 \
                -p 7444:7444 \
                -p 3000:3000 \
                -v mg_lib:/var/lib/memgraph \
                memgraph/memgraph-platform
            
            echo "✓ Memgraph started"
            echo "  - Bolt port: 7687"
            echo "  - HTTP port: 7444"
            echo "  - Lab UI: http://localhost:3000"
        fi
    fi
else
    echo "⚠️  Docker not found"
    echo "   To use code-graph-rag features, install Docker and run:"
    echo "   docker run -d -p 7687:7687 -p 7444:7444 -p 3000:3000 memgraph/memgraph-platform"
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys"
echo "2. Start Memgraph if not already running (see above)"
echo "3. Run your first code analysis:"
echo "   python -c 'from agent_team.tools.code_graph_tools import ingest_codebase; print(ingest_codebase())'"
echo "   # to wipe existing graph data first, pass clear_existing=True"
echo "   python -c 'from agent_team.tools.code_graph_tools import ingest_codebase; print(ingest_codebase(clear_existing=True))'"
echo ""
echo "For more information, see:"
echo "  - CODE_GRAPH_INTEGRATION.md - Integration guide"
echo "  - README.md - Main documentation"
echo ""
