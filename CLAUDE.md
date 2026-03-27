# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`viyv_mcp` is a Python package that wraps the MCP SDK and Starlette to quickly create MCP (Model Context Protocol) servers with minimal boilerplate. It provides decorator-based APIs for tools, resources, and prompts.

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
  - `core.py` - ViyvMCP class that assembles the ASGI app with McpServer and Starlette
  - `decorators.py` - Decorator implementations (@tool, @resource, @prompt, @entry)
  - `server/` - McpServer, McpRegistry (direct mcp SDK wrapper)
  - `cli.py` - CLI for project generation (`create-viyv-mcp`)
  - `agent_runtime.py` - Agent runtime utilities for tool execution
  - `app/` - Core application components
    - `config.py` - Configuration management (HOST, PORT, STATELESS_HTTP, etc.)
    - `registry.py` - Auto-registration of modules
    - `bridge_manager.py` - External MCP server management
    - `entry_registry.py` - Registry for FastAPI app entries
    - `mcp_initialize_fix.py` - Pydantic v2 compatibility patches for MCP protocol
    - `lifespan.py` - Application lifespan management
    - `security/` - JWT authentication and access control subsystem
      - `domain/models.py` - AgentIdentity, ToolSecurityMeta, AuthResult, AuthMode
      - `domain/policy.py` - Pure authorization functions (namespace, clearance)
      - `infrastructure/jwt_codec.py` - PyJWT encode/decode wrapper
      - `infrastructure/config_loader.py` - SecurityConfig (Pydantic), YAML + env var
      - `infrastructure/audit_writer.py` - Structured JSON audit logging
      - `service.py` - SecurityService (authentication, authorization, audit orchestration)
      - `tool_registry.py` - ToolSecurityRegistry (thread-safe metadata store)
      - `context.py` - ContextVar for agent identity (stdio/HTTP bridge)
      - (Security checks are in McpServer handlers, not a separate middleware)
      - `asgi_jwt_extractor.py` - ASGI middleware for HTTP JWT extraction
  - `__main__.py` - CLI for `python -m viyv_mcp generate-jwt`
  - `templates/` - Project template files

### Key Design Patterns

1. **Decorator-Based Registration**: Tools, resources, and prompts are registered using decorators (`@tool`, `@resource`, `@prompt`) that automatically find the `McpServer` instance from the call stack.

2. **Auto-Registration**: Modules in specific directories (`app/tools/`, `app/resources/`, etc.) are automatically imported and registered if they have a `register(mcp)` function.

3. **External MCP Bridge**: JSON config files in `app/mcp_server_configs/` define external MCP servers to launch and bridge automatically.

4. **McpServer (Direct mcp SDK)**: Uses `mcp.server.lowlevel.Server` directly — no FastMCP. `McpServer` (`viyv_mcp/server/mcp_server.py`) owns tool/resource/prompt registries, handles MCP protocol, and provides stdio + StreamableHTTP transports.

5. **ASGI Architecture**: Custom ASGI-level routing that sends `/mcp` paths directly to the MCP app, bypassing Starlette middleware to fix SSE streaming issues.

6. **Stateless HTTP Support**: Enables stateless HTTP connections for multi-worker deployments. When enabled, session IDs are not required for MCP requests.

7. **JWT Security (ContextVar + Handler-level checks)**: Agent identity established via JWT, enforced at McpServer handler level (works for both stdio and HTTP). ASGI middleware extracts JWT from HTTP Authorization headers and stores in ContextVar. For stdio, JWT is validated once at startup. Namespace controls tool visibility (tools/list filtering), numeric security_level controls tool executability (tools/call clearance check). Clearance and security_level are integers where lower = higher privilege. Access rule: `jwt.clearance <= tool.security_level`.

### Code Examples

#### Creating a Tool
```python
from viyv_mcp import tool

def register(mcp):
    @tool(description="Add two numbers", tags={"calc"})
    def add(a: int, b: int) -> int:
        return a + b

    # Tool with security metadata
    @tool(
        description="Query employee salary",
        namespace="hr",                 # Visible only to agents with hr namespace
        security_level=1,              # Requires clearance <= 1 (0=highest privilege)
    )
    def query_salary(employee_id: str) -> str:
        return f"Salary for {employee_id}: $100,000"
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
  "cwd": "/path/to/working/directory",
  "tags": ["filesystem", "git"],
  "namespace": "hr",
  "security_level": 1,
  "namespace_map": { "public_stats": "common" },
  "security_level_map": { "update_salary": 0 }
}
```

### Integration Points

- **Custom Endpoints**: Use `@entry(path)` decorator to mount additional FastAPI apps
  - Dynamic tool middleware injection
  - Automatic tool refresh on requests

## Environment Variables

### Server
- `HOST` - Server host (default: 127.0.0.1)
- `PORT` - Server port (default: 8000)
- `BRIDGE_CONFIG_DIR` - Directory for MCP server configs (default: app/mcp_server_configs)
- `STATIC_DIR` - Static files directory (default: static/images)
- `STATELESS_HTTP` - Enable stateless HTTP mode for multi-worker support (true/false, default: None)
  - Values: "true", "1", "yes", "on" → True
  - Values: "false", "0", "no", "off" → False
  - When True: Session IDs are not required for MCP requests
  - When False: Session management is enabled (default MCP behavior)

### Security (JWT Authentication & Access Control)
- `VIYV_MCP_AUTH` - Security mode: "bypass" (no checks), or omit to auto-detect
  - If `VIYV_MCP_JWT_SECRET` is set → authenticated mode
  - If neither `VIYV_MCP_AUTH` nor `VIYV_MCP_JWT_SECRET` is set → deny_all mode
  - bypass mode logs a warning at startup and is blocked when `VIYV_MCP_ENV=production`
- `VIYV_MCP_JWT_SECRET` - HS256 shared secret for JWT validation (required for authenticated mode)
- `VIYV_MCP_JWT` - JWT token for stdio authentication (validated once at startup, process-scoped)
- `VIYV_MCP_ENV` - Set to "production" to block bypass mode
- `VIYV_MCP_AUDIT_LOG` - Path to audit log file (JSONL format); defaults to stderr
- `VIYV_SECURITY_CONFIG` - Path to security.yaml config file (default: security.yaml, optional)

## Testing Approach

The repository has two testing approaches:

### Unit & E2E tests (pytest)
```bash
pytest test/test_security/ -v   # Security subsystem: 68 tests
```
The `test/test_security/` directory contains comprehensive tests:
- `test_domain/` - Pure policy and model tests (no mocks)
- `test_infrastructure/` - JWT codec, config loader tests
- `test_service.py` - SecurityService integration tests
- `test_e2e.py` - End-to-end tests through McpServer handlers + HTTP

### Manual / example testing
The `example/` directory contains sample implementations. Test new functionality by:
1. Adding sample implementations in the test project
2. Running the server with `uv run python main.py`
3. Testing endpoints manually or with tools like curl/httpie

## Package Dependencies
Core dependencies include:
- `mcp>=1.26.0` - MCP protocol implementation (direct SDK, no FastMCP)
- `starlette>=0.25.0` - ASGI framework
- `uvicorn>=0.22.0` - ASGI server
- `pytest>=7.0` - Testing framework
- `pydantic>=2` - Data validation (v2 compatibility focus)
- `PyJWT>=2.0` - JWT token encoding/decoding for security

Optional dependencies:
- `PyYAML>=6.0` - For security.yaml config file support (`pip install 'viyv_mcp[security]'`)

## Important Notes

- When creating new modules, always define a `register(mcp)` function
- External MCP configs require `command` and `args` fields in JSON
- Static files are served from the path configured in `STATIC_DIR`
- All decorators work by finding the McpServer instance from the call stack
- The package is distributed on PyPI as `viyv_mcp` (current version: 2.0.0)
- Generated projects use `uv` for dependency management via `pyproject.toml`
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
- Use `Annotated` and `Field` from pydantic for parameter definitions
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

### Security Issues
- **bypass mode not starting**: `VIYV_MCP_ENV=production` blocks bypass mode. Remove or change VIYV_MCP_ENV
- **"Authentication failed" errors**: Check that `VIYV_MCP_JWT_SECRET` matches the secret used to sign the JWT
- **"Tool not found" for existing tools**: The tool's namespace is not in the agent's trusted namespaces. Check JWT `namespace` and `trust` claims
- **"insufficient clearance" errors**: Agent's numeric `clearance` is greater than the tool's `security_level` (lower number = higher privilege; rule: `clearance <= security_level`)
- **JWT generation**: Use `python -m viyv_mcp generate-jwt --sub agent --clearance 2 --namespace hr --trust common --expires 24h --secret $SECRET`
- **Audit log location**: Set `VIYV_MCP_AUDIT_LOG=/path/to/audit.jsonl` or check stderr for audit records
- **stdio mode**: Set `VIYV_MCP_JWT` env var; identity is validated once at startup and fixed for process lifetime