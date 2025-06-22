# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`viyv_mcp` is a Python package that wraps FastMCP and Starlette to quickly create MCP (Model Context Protocol) servers with minimal boilerplate. It provides decorator-based APIs for tools, resources, prompts, and agents, plus adapters for Slack and OpenAI Agents integration.

## Development Commands

### Core Package Development
```bash
# Install dependencies (using uv)
uv sync

# Run tests
pytest

# Build the package
python -m build

# Install locally for development
pip install -e .

# Create a new project from template
create-viyv-mcp new <project_name>

# Publishing to PyPI
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/*
```

### Generated Project Commands
When working with projects created via `create-viyv-mcp`:
```bash
# Install dependencies
uv sync

# Run the server
uv run python main.py

# The server runs on 0.0.0.0:8000 by default
# Health check: GET /health returns {"status":"ok"}
```

## Architecture

### Package Structure
- **`viyv_mcp/`** - Main package
  - `core.py` - ViyvMCP class that assembles the ASGI app with FastMCP and Starlette
  - `decorators.py` - Decorator implementations (@tool, @resource, @prompt, @agent, @entry)
  - `cli.py` - CLI for project generation (`create-viyv-mcp`)
  - `openai_bridge.py` - Converts FastMCP tools to OpenAI Agents SDK functions
  - `agent_runtime.py` - Agent runtime utilities for tool execution
  - `run_context.py` - Context management for Slack and other integrations
  - `app/` - Core application components
    - `config.py` - Configuration management (HOST, PORT, etc.)
    - `registry.py` - Auto-registration of modules
    - `bridge_manager.py` - External MCP server management
    - `entry_registry.py` - Registry for FastAPI app entries
    - `adapters/slack_adapter.py` - Slack event handling and integration
  - `templates/` - Project template files

### Key Design Patterns

1. **Decorator-Based Registration**: Tools, resources, prompts, and agents are registered using decorators that automatically find the FastMCP instance from the call stack.

2. **Auto-Registration**: Modules in specific directories (`app/tools/`, `app/resources/`, etc.) are automatically imported and registered if they have a `register(mcp: FastMCP)` function.

3. **External MCP Bridge**: JSON config files in `app/mcp_server_configs/` define external MCP servers to launch and bridge automatically.

4. **Dynamic Tool Injection**: Tools are refreshed on every request to ensure agents have the latest available tools.

5. **ASGI Architecture**: Built on Starlette with FastMCP mounted at `/mcp` by default, supporting SSE-based communication.

6. **RunContextWrapper Pattern**: Tools receive a `RunContextWrapper[RunContext]` parameter that provides access to context like Slack events and user information.

### Code Examples

#### Creating a Tool
```python
from viyv_mcp import tool
from viyv_mcp.run_context import RunContext
from agents import RunContextWrapper

def register(mcp: FastMCP):
    @tool(description="Add two numbers", tags={"calc"})
    def add(
        wrapper: RunContextWrapper[RunContext],
        a: int,
        b: int
    ) -> int:
        return a + b
```

#### Creating an Agent
```python
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools

@agent(name="calculator", use_tools=["add", "subtract"])
async def calculator_agent(query: str) -> str:
    oa_tools = build_function_tools(use_tools=["add", "subtract"])
    # Agent implementation using OpenAI SDK
```

#### Adding Custom Endpoints
```python
from viyv_mcp import entry
from fastapi import FastAPI

@entry("/api")
def create_api():
    app = FastAPI()
    @app.get("/status")
    def status():
        return {"status": "running"}
    return app
```

#### External MCP Server Configuration
Create JSON files in `app/mcp_server_configs/`:
```json
{
  "command": "node",
  "args": ["path/to/mcp-server.js"],
  "env": {
    "API_KEY": "$API_KEY"
  }
}
```

### Integration Points

- **Slack**: Use `SlackAdapter` to handle Slack events and attachments
- **OpenAI Agents**: Use `build_function_tools()` to convert MCP tools for OpenAI Agents SDK
- **Custom Endpoints**: Use `@entry(path)` decorator to mount additional FastAPI apps

## Environment Variables

- `HOST` - Server host (default: 127.0.0.1)
- `PORT` - Server port (default: 8000)
- `BRIDGE_CONFIG_DIR` - Directory for MCP server configs (default: app/mcp_server_configs)
- `STATIC_DIR` - Static files directory (default: static/images)

## Testing Approach

The repository includes a `test/` directory with sample implementations rather than unit tests. Test new functionality by:
1. Adding sample implementations in the test project
2. Running the server with `uv run python main.py`
3. Testing endpoints manually or with tools like curl/httpie

## Package Dependencies
Core dependencies include:
- `fastmcp>=2.3.3` - MCP protocol implementation
- `starlette>=0.25.0` - ASGI framework
- `uvicorn>=0.22.0` - ASGI server
- `slack-bolt>=1.23.0` - Slack integration
- `openai-agents>=0.0.13` - OpenAI Agents SDK integration
- `pytest>=7.0` - Testing framework

## Important Notes

- When creating new modules, always define a `register(mcp: FastMCP)` function
- External MCP configs require `command` and `args` fields in JSON
- The `@agent` decorator creates both a tool and registers it in the agent registry
- Static files are served from the path configured in `STATIC_DIR`
- All decorators work by finding the FastMCP instance from the call stack
- The package is distributed on PyPI as `viyv_mcp` (current version: 0.1.3)
- Generated projects use `uv` for dependency management via `pyproject.toml`
- Tools using RunContextWrapper can access Slack events and user context when available