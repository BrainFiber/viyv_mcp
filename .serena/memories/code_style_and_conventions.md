# Code Style and Conventions

## Language and Comments
- **Primary Language**: Python 3.10+
- **Comments**: Japanese comments are commonly used in the codebase (特にサンプルコード)
- **Documentation**: Both English (README, CLAUDE.md) and Japanese (inline comments) supported

## Type Annotations

### Required Type Hints
- **ALL functions must have type hints** for parameters and return values
- Use `typing` module for complex types: `List`, `Dict`, `Optional`, `Annotated`, etc.

### Parameter Definitions with Pydantic
Use `Annotated` + `Field` from Pydantic for rich parameter metadata:

```python
from typing import Annotated, List
from pydantic import Field

@tool(description="Add two numbers", tags={"calc"})
def add(
    a: Annotated[int, Field(title="被加数", description="1 つ目の整数")],
    b: Annotated[int, Field(title="加数", description="2 つ目の整数")],
) -> int:
    """a + b を計算して返す"""
    return a + b
```

**Key Points**:
- `title`: Japanese/English field title
- `description`: Detailed parameter description
- `default`: Optional default values
- `min_items`, `max_items`: For List validation
- Field metadata appears in JSON Schema for MCP tools

## Decorator Patterns

### Tool Registration Pattern
Every module in `app/tools/`, `app/resources/`, `app/prompts/`, `app/agents/` must define:

```python
from fastmcp import FastMCP
from viyv_mcp import tool  # or resource, prompt, agent

def register(mcp: FastMCP):
    """Auto-registration function called by the framework"""
    
    @tool(description="Tool description", tags={"category"})
    def my_tool(param: str) -> str:
        return param
```

**Important**:
- Function name MUST be `register(mcp: FastMCP)`
- Decorators automatically find MCP instance from call stack
- No need to explicitly pass `mcp` to decorators

### Available Decorators

1. **@tool** - Register MCP tools
   ```python
   @tool(description="...", tags={"tag1", "tag2"})
   def tool_name(params) -> result:
       ...
   ```

2. **@resource** - Register MCP resources
   ```python
   @resource("uri_template://{param}")
   def resource_name(param: str) -> dict:
       ...
   ```

3. **@prompt** - Register MCP prompts
   ```python
   @prompt("prompt_name")
   def prompt_name(param: str) -> str:
       ...
   ```

4. **@agent** - Register AI agents
   ```python
   @agent(name="agent_name", use_tools=["tool1", "tool2"])
   async def agent_name(query: str) -> str:
       ...
   ```

5. **@entry** - Mount custom FastAPI endpoints
   ```python
   @entry("/api/path")
   def create_api():
       app = FastAPI()
       # define routes
       return app
   ```

## RunContextWrapper Pattern

For tools that need runtime context (Slack events, user info):

```python
from viyv_mcp.run_context import RunContext
from agents import RunContextWrapper

@tool(description="Get context info")
def context_tool(
    wrapper: RunContextWrapper[RunContext],
    other_param: str
) -> dict:
    context = wrapper.context
    if context and hasattr(context, 'slack_event'):
        # Access Slack event data
        return {"user": context.slack_event.get("user")}
    return {"param": other_param}
```

**Key Points**:
- `RunContextWrapper[RunContext]` is the FIRST parameter
- Signature is manipulated for dual compatibility (FastMCP + OpenAI SDK)
- Context may be None, always check before accessing

## Module Organization

### Directory Structure
```
app/
├── config.py              # Configuration class
├── tools/                 # MCP tools
│   └── sample_math_tools.py
├── resources/             # MCP resources
│   └── sample_echo_resource.py
├── prompts/               # MCP prompts
│   └── sample_prompt.py
├── agents/                # AI agents
│   └── sample_calc_agent.py
├── entries/               # Custom HTTP endpoints
│   └── sample_health.py
└── mcp_server_configs/    # External MCP server configs (JSON)
    └── filesystem.json
```

### File Naming
- Use snake_case for file names: `sample_math_tools.py`
- Descriptive names indicating content: `slack_adapter.py`, `openai_bridge.py`
- Prefix samples with `sample_`: `sample_calc_agent.py`

## External MCP Server Configuration

JSON format in `app/mcp_server_configs/`:

```json
{
  "command": "npx",
  "args": ["@modelcontextprotocol/server-filesystem", "/workspace"],
  "env": {
    "API_KEY": "$API_KEY"
  },
  "cwd": "/path/to/working/dir",
  "tags": ["filesystem", "io"]
}
```

**Required Fields**:
- `command`: Executable command
- `args`: Command arguments array

**Optional Fields**:
- `env`: Environment variables (use `$VAR_NAME` for interpolation)
- `cwd`: Working directory
- `tags`: Tags for filtering tools

## Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning messages")
logger.error("Error messages")
```

## Async/Await Patterns

- Use `async def` for agents and async operations
- Decorators support both sync and async functions
- External MCP communication is async with aiohttp

## Error Handling

- Gracefully handle missing optional directories (tools, resources, etc.)
- Use try/except for external service calls
- Log errors with appropriate context
- Return meaningful error messages to users

## Testing Patterns

- Sample implementations in `test/` directory (not unit tests)
- Test by running server: `uv run python main.py`
- Manual testing with curl/httpie or MCP clients
- Integration testing with example projects
