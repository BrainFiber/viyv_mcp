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

# When testing in example projects, install viyv_mcp in editable mode
cd example/test  # or any example project
uv pip install -e ../../  # Install viyv_mcp from parent directory

# Create a new project from template
create-viyv-mcp new <project_name>

# Publishing to PyPI
pip install build twine  # Install build tools if needed
rm -rf dist/ build/ *.egg-info
python -m build
# Optional: Test upload to TestPyPI first
twine upload --repository testpypi dist/*
# Production upload
twine upload dist/*
```

### Generated Project Commands
When working with projects created via `create-viyv-mcp`:
```bash
# Install dependencies
uv sync

# Run the server (single worker)
uv run python main.py

# Run with stateless HTTP mode (for multi-worker support)
STATELESS_HTTP=true uv run python main.py

# Production deployment with multiple workers (requires gunicorn)
uv pip install gunicorn
STATELESS_HTTP=true uv run gunicorn test_app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

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
    - `config.py` - Configuration management (HOST, PORT, STATELESS_HTTP, etc.)
    - `registry.py` - Auto-registration of modules
    - `bridge_manager.py` - External MCP server management
    - `entry_registry.py` - Registry for FastAPI app entries
    - `mcp_initialize_fix.py` - Pydantic v2 compatibility patches for MCP protocol
    - `lifespan.py` - Application lifespan management
    - `adapters/slack_adapter.py` - Slack event handling and integration
  - `templates/` - Project template files

### Key Design Patterns

1. **Decorator-Based Registration**: Tools, resources, prompts, and agents are registered using decorators that automatically find the FastMCP instance from the call stack.

2. **Auto-Registration**: Modules in specific directories (`app/tools/`, `app/resources/`, etc.) are automatically imported and registered if they have a `register(mcp: FastMCP)` function.

3. **External MCP Bridge**: JSON config files in `app/mcp_server_configs/` define external MCP servers to launch and bridge automatically.

4. **Dynamic Tool Injection**: Tools are refreshed on every request to ensure agents have the latest available tools.

5. **ASGI Architecture**: Custom ASGI-level routing that sends `/mcp` paths directly to the MCP app, bypassing Starlette middleware to fix SSE streaming issues.

6. **RunContextWrapper Pattern**: Tools receive a `RunContextWrapper[RunContext]` parameter that provides access to context like Slack events and user information. The signature is manipulated to work with both FastMCP and OpenAI Agents SDK.

7. **Signature Manipulation**: The decorator system manipulates function signatures to support `RunContextWrapper` for agent execution while maintaining clean JSON Schema generation for FastMCP.

8. **Stateless HTTP Support**: New feature (v0.1.10) that enables stateless HTTP connections for multi-worker deployments. When enabled, session IDs are not required for MCP requests.

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
  },
  "cwd": "/path/to/working/directory",  // Optional: working directory
  "tags": ["filesystem", "git"]          // Optional: tags for filtering
}
```

### Integration Points

- **Slack**: Use `SlackAdapter` to handle Slack events and attachments
  - Full event handling with `@app_mention` support
  - File upload/download capabilities
  - Thread history building for conversation context
  - Channel prompt extraction from topic/purpose
  - RunContext integration for tool access

- **OpenAI Agents**: Use `build_function_tools()` to convert MCP tools for OpenAI Agents SDK
  - Function tool conversion with Pydantic validation
  - Schema transformation (removes `default` keys, sets all fields as required)
  - RunContextWrapper parameter injection
  - Async wrapper for synchronous functions

- **Custom Endpoints**: Use `@entry(path)` decorator to mount additional FastAPI apps
  - Dynamic tool middleware injection
  - Automatic tool refresh on requests

## Environment Variables

- `HOST` - Server host (default: 127.0.0.1)
- `PORT` - Server port (default: 8000)
- `BRIDGE_CONFIG_DIR` - Directory for MCP server configs (default: app/mcp_server_configs)
- `STATIC_DIR` - Static files directory (default: static/images)
- `STATELESS_HTTP` - Enable stateless HTTP mode for multi-worker support (true/false, default: None)
  - Values: "true", "1", "yes", "on" → True
  - Values: "false", "0", "no", "off" → False
  - When True: Session IDs are not required for MCP requests
  - When False: Session management is enabled (default FastMCP behavior)

## Testing Approach

The repository includes a `test/` directory with sample implementations rather than unit tests. Test new functionality by:
1. Adding sample implementations in the test project
2. Running the server with `uv run python main.py`
3. Testing endpoints manually or with tools like curl/httpie

## Package Dependencies
Core dependencies include:
- `fastmcp>=2.12.3` - MCP protocol implementation (recently upgraded for better compatibility)
- `starlette>=0.25.0` - ASGI framework
- `uvicorn>=0.22.0` - ASGI server
- `slack-bolt>=1.23.0` - Slack integration
- `openai-agents>=0.0.13` - OpenAI Agents SDK integration
- `pytest>=7.0` - Testing framework
- `pydantic>=2` - Data validation (v2 compatibility focus)
- `aiohttp>=3.11.18` - Async HTTP client

## Important Notes

- When creating new modules, always define a `register(mcp: FastMCP)` function
- External MCP configs require `command` and `args` fields in JSON
- The `@agent` decorator creates both a tool and registers it in the agent registry
- Static files are served from the path configured in `STATIC_DIR`
- All decorators work by finding the FastMCP instance from the call stack
- The package is distributed on PyPI as `viyv_mcp` (current version: 0.1.10)
- Generated projects use `uv` for dependency management via `pyproject.toml`
- Tools using RunContextWrapper can access Slack events and user context when available
- The test/ directory contains working examples rather than unit tests - use these as reference implementations
- External MCP servers are managed as child processes with stdio-based communication
- ASGI-level routing fixes SSE streaming issues that occurred with middleware
- MCP protocol version 2024-11-05 is supported with Pydantic v2 compatibility patches

## Production Deployment

### Multi-Worker Support
For production environments requiring multiple workers:

1. **Enable Stateless HTTP Mode**:
   ```bash
   export STATELESS_HTTP=true
   ```

2. **Use Gunicorn with Uvicorn Workers**:
   ```bash
   # Install gunicorn
   uv pip install gunicorn

   # Run with 4 workers
   STATELESS_HTTP=true uv run gunicorn test_app:app \
     -w 4 \
     -k uvicorn.workers.UvicornWorker \
     -b 0.0.0.0:8000
   ```

3. **Create a startup module** (test_app.py):
   ```python
   from viyv_mcp import ViyvMCP
   from app.config import Config

   stateless_http = Config.get_stateless_http()
   app = ViyvMCP("My MCP Server", stateless_http=stateless_http).get_app()
   ```

### Performance Considerations
- **Dynamic Tool Injection**: Tools are refreshed on every request, which may impact performance with many tools
- **External MCP Bridges**: Each external server runs as a child process; monitor resource usage
- **SSE Streaming**: Custom ASGI routing ensures efficient SSE streaming without middleware interference
- **Session Management**: Use `STATELESS_HTTP=true` for better scalability in multi-worker setups

## File Placement Guidelines

When creating scripts or files during development with Claude Code:

### Permanent Scripts and Tools
Place in the following locations based on purpose:
- **Development scripts**: `scripts/` directory (create if needed)
  - Build automation scripts
  - Deployment helpers
  - Development utilities
- **Test utilities**: `test/utils/` directory
  - Test data generators
  - Testing helper scripts

### Temporary Files
Use these locations for temporary work that can be deleted anytime:
- **`tmp/`** directory (create if needed) - For all temporary scripts and experiments
- **`scratch/`** directory - Alternative for quick experiments
- **`.tmp/`** directory - For hidden temporary files

**Important**: Add `tmp/`, `scratch/`, and `.tmp/` to `.gitignore` to prevent accidental commits of temporary files.

### Never Place Files In:
- Root directory (unless it's a configuration file like `.env`)
- Inside `viyv_mcp/` package directory (unless adding new features)
- Random subdirectories without clear purpose

## MCP Tool Development Guidelines

### Tool Parameter Type Annotations
- Use `Annotated` and `Field` from FastMCP for parameter definitions
- Example: `query: Annotated[str, Field(description="Search query")]`
- Optional parameters should have default values

### Claude CLI Integration
- The `--resume` feature uses session IDs to continue conversations
- Use JSON format for session persistence
- Protect file access in async operations with `asyncio.Lock()`

### ChatGPT Compatibility Requirements
For ChatGPT integration, these tools are mandatory:
- **`search`** tool: Must accept `query` parameter (required) and return results in `resource_link` format
- **`fetch`** tool: Must accept `id` parameter (required) - note this is an ID, not a URI
- The `annotations` parameter is not currently supported in viyv_mcp

### MCP Protocol Notes
- Protocol version: 2024-11-05 (with compatibility patches for older versions)
- tools/list requests require a valid session ID (unless `STATELESS_HTTP=true`)
- initialize requests must include `protocolVersion` and `capabilities`
- clientInfo field is patched for Pydantic v2 compatibility in mcp_initialize_fix.py

## Troubleshooting

### SSE Streaming Issues
- The custom ASGI routing in `core.py` routes `/mcp` paths directly to avoid middleware conflicts
- If SSE streaming fails, check that no additional middleware is interfering with the `/mcp` path

### Protocol Compatibility
- Pydantic v2 validation errors are patched in `mcp_initialize_fix.py`
- If initialization fails with validation errors, check the MCP protocol version

### Multi-Worker Issues
- Uvicorn's `--workers` flag doesn't work well with the dynamic app creation
- Use Gunicorn with UvicornWorker for proper multi-worker support
- Always enable `STATELESS_HTTP=true` for multi-worker deployments

### External MCP Server Issues
- Check that the `command` exists and is executable
- Environment variables in configs use `$VAR_NAME` syntax
- Working directory (`cwd`) must exist if specified
- Child processes are managed automatically; check logs for startup errors