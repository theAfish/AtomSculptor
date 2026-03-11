#!/bin/bash
# Installation script for AtomSculptor with code-graph-rag integration

set -e  # Exit on error

echo "=========================================="
echo "AtomSculptor Installation"
echo "=========================================="

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python $REQUIRED_VERSION or higher is required (found: $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python version OK: $PYTHON_VERSION"

# Install main dependencies
echo ""
echo "Installing AtomSculptor dependencies..."
pip install -e .

# # quickly verify that the local code_graph_rag package is importable
# python - <<'PYCODE'
# try:
#     import code_graph_rag
#     print("✓ code_graph_rag importable")
# except ImportError:
#     echo "⚠️  code_graph_rag not importable – check pyproject.toml package configuration"
#     exit 1
# PYCODE

# Ask about optional dependencies
echo ""
read -p "Install full tree-sitter language support? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing tree-sitter language parsers..."
    pip install -e ".[treesitter-full]"
fi

# Ask about dev dependencies
echo ""
read -p "Install development dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing development dependencies..."
    pip install -e ".[dev]"
fi

# Check for .env file
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo "⚠️  Please edit .env and add your API keys"
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
