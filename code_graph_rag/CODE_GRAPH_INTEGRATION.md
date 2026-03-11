# Code-Graph-RAG Integration Guide

This document explains how the `code-graph-rag` module has been integrated into the AtomSculptor project and how to use it.

## Overview

The code-graph-rag module provides graph-based Retrieval-Augmented Generation (RAG) capabilities for codebase analysis. It uses Memgraph as a graph database to store and query code relationships, enabling powerful code understanding and analysis features.

## What Was Integrated

### 1. Dependencies
All code-graph-rag dependencies have been merged into the main `pyproject.toml`:
- Memgraph client (`pymgclient`)
- Tree-sitter for code parsing
- Pydantic-AI for AI tooling
- Additional utilities (loguru, watchdog, diff-match-patch, etc.)

### 2. Configuration
Extended `settings.py` and `config.yaml` to include:
- **Memgraph settings**: Host, port, HTTP port, Lab port
- **LLM provider settings**: Support for Gemini, DeepSeek, and local models
- **Model IDs**: For various Gemini and local models
- **API keys**: Gemini, DeepSeek, GCP, OpenAI
- **Repository settings**: Target repo path, shell command timeout

### 3. New Agent: `code_analyzer`
Created a new agent specialized in codebase analysis with the following tools:
- `ingest_codebase`: Index a codebase into the graph database
- `query_codebase_structure`: Query code structure using natural language
- `find_code_snippet`: Find specific code by qualified name
- `analyze_code_relationships`: Analyze code dependencies and relationships
- `search_code`: Search for code patterns and entities

### 4. Agent Integration
The `code_analyzer` agent has been integrated into the agent team:
- Added as a sub-agent to the `planner`
- Registered with the sandbox system

  > 💡 **Note:** The code-graph tools and `code_analyzer` agent are normal
  > Python modules located outside of `sandbox/`. They don’t need to live in
  > the sandbox tree; the graph code lives in `code_graph_rag` alongside the
  > rest of the project.

- Available for delegation by the planner agent

## Installation

1. **Install dependencies**:
   ```bash
   pip install -e .
   ```

   > ⚠️ *If you still see ``code-graph-rag module not found`` after installing,
   > it usually means the local package wasn’t included in the build. Earlier
   > versions of the project used `code-graph-rag` (with a hyphen) in the
   > `pyproject.toml` `packages.find.where` list which doesn’t match the actual
   > directory name (`code_graph_rag`). The configuration has now been fixed;
   > reinstalling with `pip install -e .` will pull in the package and the
   > warning should disappear.*

   For full tree-sitter language support:
   ```bash
   pip install -e ".[treesitter-full]"
   ```

2. **Install and start Memgraph**:
   
   Using Docker:
   ```bash
   docker run -it -p 7687:7687 -p 7444:7444 -p 3000:3000 \
     -v mg_lib:/var/lib/memgraph \
     memgraph/memgraph-platform
   ```
   
   Or use the provided `docker-compose.yaml` if available.

3. **Configure environment variables** (optional, defaults are provided):
   
   Create a `.env` file:
   ```bash
   # Memgraph settings (defaults shown)
   MEMGRAPH_HOST=localhost
   MEMGRAPH_PORT=7687
   MEMGRAPH_HTTP_PORT=7444
   LAB_PORT=3000
   
   # LLM Provider (options: gemini, deepseek, local)
   LLM_PROVIDER=deepseek
   
   # API Keys (as needed)
   DEEPSEEK_API_KEY=your_key_here
   GEMINI_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   
   # Target repository for analysis (optional, defaults to current directory)
   TARGET_REPO_PATH=/path/to/your/repo
   ```

## Usage

### Using the Code Analyzer Agent

The code analyzer agent can be invoked through the planner for codebase analysis tasks:

```python
# Example: Ask the planner to analyze code
"Analyze the structure of the agent_team module and show me all the agents"

# Example: Find a specific function
"Find the code for the create_plan function"

# Example: Analyze dependencies
"What are all the imports used by the planner agent?"

# Example: Search for code patterns
"Search for all classes that inherit from Agent"
```

### Direct Tool Usage

> **New option:** the ``ingest_codebase`` helper now accepts a
> ``clear_existing`` boolean.  Setting it to ``True`` will first delete all
> nodes and relationships in Memgraph, ensuring a completely fresh index.  This
> is handy when the repository path changes or you want to drop stale data.


The code graph tools can also be used directly in Python:

```python
from agent_team.tools.code_graph_tools import (
    ingest_codebase,
    query_codebase_structure,
    find_code_snippet,
    analyze_code_relationships,
    search_code,
)

# Ingest a codebase
# wipe out any existing graph data before ingesting
result = ingest_codebase(repo_path="/path/to/repo", clear_existing=True)
print(result)

# or just re-run without clearing; merges based on node keys
result = ingest_codebase(repo_path="/path/to/repo")
print(result)

# Query the structure
result = query_codebase_structure("Agent")
print(result)

# Find specific code
result = find_code_snippet("agent_team.agents.planner.planner")
print(result)

# Analyze relationships
result = analyze_code_relationships("planner", relationship_type="imports")
print(result)

# Search for code
result = search_code("Agent", entity_type="Class")
print(result)
```

### Workflow Example

1. **Ingest the codebase**:
   ```
   Ask planner: "Ingest the AtomSculptor codebase for analysis"
   ```

2. **Explore the structure**:
   ```
   Ask planner: "What agents are available in the codebase?"
   ```

3. **Find specific code**:
   ```
   Ask planner: "Show me the implementation of the structure_builder agent"
   ```

4. **Analyze dependencies**:
   ```
   Ask planner: "What modules does the planner agent import?"
   ```

## Configuration Details

### Memgraph Configuration
- **MEMGRAPH_HOST**: Hostname for Memgraph (default: `localhost`)
- **MEMGRAPH_PORT**: Bolt protocol port (default: `7687`)
- **MEMGRAPH_HTTP_PORT**: HTTP port (default: `7444`)
- **LAB_PORT**: Memgraph Lab UI port (default: `3000`)

### LLM Provider Configuration
- **LLM_PROVIDER**: Choose between `gemini`, `deepseek`, or `local`
- **GEMINI_PROVIDER**: For Gemini, choose between `gla` (API) or `vertex` (Vertex AI)
- Model IDs are configurable for different tasks (orchestration, Cypher generation, etc.)

### Repository Settings
- **TARGET_REPO_PATH**: Path to the repository to analyze (defaults to current workspace)
- **SHELL_COMMAND_TIMEOUT**: Timeout for shell commands in seconds (default: `30`)

## Architecture

### Integration Points

1. **Settings Layer**: `settings.py` provides unified configuration management
2. **Tools Layer**: `agent_team/tools/code_graph_tools.py` wraps code-graph-rag for Google ADK
3. **Agent Layer**: `agent_team/agents/code_analyzer.py` provides the agent interface
4. **Orchestration**: The planner agent coordinates all sub-agents including code analyzer

### Data Flow

```
User Request
    ↓
Planner Agent
    ↓
Code Analyzer Agent
    ↓
Code Graph Tools
    ↓
Memgraph Database ←→ Codebase Files
    ↓
Results
```

## Troubleshooting

### Memgraph Connection Issues
- Ensure Memgraph is running: `docker ps | grep memgraph`
- Check port availability: `netstat -an | grep 7687`
- Verify connection settings in `.env` or `config.yaml`

### Import Errors
- If you see "code-graph-rag module not found", reinstall dependencies:
  ```bash
  pip install -e .
  ```
- Check that `codebase_rag` package is properly installed:
  ```bash
  python -c "import codebase_rag; print(codebase_rag.__file__)"
  ```

### Ingestion Issues
- Ensure the target repository path exists and is readable
- Check that tree-sitter is properly installed for your language
- Review Memgraph logs for any database errors

## Next Steps

### Potential Enhancements
1. **Add documentation scraping**: Integrate markdown/documentation analysis
2. **Implement code generation**: Use the graph for context-aware code generation
3. **Add visualization**: Create visual representations of code relationships
4. **Extend language support**: Add more tree-sitter parsers for additional languages
5. **Implement caching**: Add caching layer for frequently accessed code snippets

### Advanced Usage
- Combine code analysis with structure building for materials informatics
- Use code graph for automated refactoring suggestions
- Integrate with CI/CD for code quality analysis

## References

- [Memgraph Documentation](https://memgraph.com/docs)
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Pydantic-AI Documentation](https://ai.pydantic.dev/)
