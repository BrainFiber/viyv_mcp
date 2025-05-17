# viyv_mcp

**viyv_mcp** is a lightweight Python wrapper around FastMCP and Starlette.
It lets you spin up a fully configured MCP server project with sample tools, resources, prompts and bridge configuration in just a few commands.

## Overview

The library provides:

- a CLI to generate a ready‐to‐run project template;
- decorator based APIs to register tools, resources, prompts and agents; and
- optional adapters for external services such as Slack or OpenAI Agents.

With these pieces you can create custom MCP servers, add your own business logic and expose the tools to any MCP compatible client.

## Why viyv_mcp?

- Launch a complete MCP server in minutes with a single command.
- Built-in adapters for Slack and OpenAI Agents reduce boilerplate when integrating external services.
- Dynamic tool injection keeps agents up to date with the latest tools on every request.
- Simple decorators for tools, prompts, resources, and agents let you focus on logic rather than wiring.

## Features

- **Quick Project Creation:**  
  Use the provided CLI command `create-viyv-mcp new <project_name>` to generate a new project template with a complete directory structure and sample files.
- **Integrated MCP Server:**  
  Automatically sets up FastMCP with Starlette and provides an SSE-based API.
- **Decorator APIs:**
  Simplify registration of tools, resources, prompts, and agents with built-in decorators (`@tool`, `@resource`, `@prompt`, and `@agent`).
- **External MCP Bridge Support:**
  Automatically launches and registers external MCP servers based on JSON config files in `app/mcp_server_configs`.
- **Health Check Endpoint:**
  Provides a `/health` endpoint to verify server status (returns `{"status":"ok"}`).
- **Slack Integration:**
  Includes a `SlackAdapter` for easily connecting a Slack workspace and handling attachments or mention events.
- **OpenAI Agents Bridge:**
  Convert FastMCP tools into OpenAI Agents SDK `FunctionTool` objects via `build_function_tools` for advanced agent workflows.
- **Dynamic Tool Injection & Entry Decorator:**
  Register additional FastAPI sub-apps with `@entry` and receive up-to-date tools on every request.
- **Template Inclusion:**
  The generated project templates include:
  - **Configuration Files:** (e.g. `app/config.py`)
  - **Prompts:** (e.g. `app/prompts/sample_prompt.py`)
  - **Resources:** (e.g. `app/resources/sample_echo_resource.py`)
  - **Tools:** (e.g. `app/tools/sample_math_tools.py`)
  - **MCP Server Configs:** (e.g. `app/mcp_server_configs/sample_slack.json`)
  - **Entries:** sample endpoints for webhook, Slack, and health check
  - **Dockerfile**, **pyproject.toml**, and **main.py** for the generated project.

## Installation

### From PyPI

Install **viyv_mcp** via pip:

```bash
pip install viyv_mcp
```

This installs the package as well as provides the CLI command `create-viyv-mcp`.

## Quick Start

### Creating a New Project Template

After installing the package, run:

```bash
create-viyv-mcp new my_mcp_project
```

This command creates a new directory called `my_mcp_project` with the following structure:

```
my_mcp_project/
├── Dockerfile
├── pyproject.toml
├── main.py
└── app/
    ├── config.py
    ├── mcp_server_configs/
    │   └── sample_slack.json
    ├── prompts/
    │   └── sample_prompt.py
    ├── resources/
    │   └── sample_echo_resource.py
    └── tools/
        └── sample_math_tools.py
```

### Running the MCP Server
1. Change into your new project directory:

   ```bash
   cd my_mcp_project
   ```

2. Use `uv` to resolve dependencies (this uses the `pyproject.toml` for dependency management):

   ```bash
   uv sync
   ```

3. Start the server with:

   ```bash
   uv run python main.py
   ```

The server will start on `0.0.0.0:8000` by default. It exposes an SSE-based API at `/` and `/messages`, provides a health-check endpoint at `/health` (returns `{"status":"ok"}`), automatically registers local modules (tools, resources, prompts), and bridges external MCP servers defined in `app/mcp_server_configs`.

### Package Structure

```text
viyv_mcp/
├── __init__.py           # Exports version, ViyvMCP, and decorators
├── core.py               # FastMCP integration and ASGI app setup
├── cli.py                # CLI command (create-viyv-mcp)
├── decorators.py         # Decorators for tool, resource, prompt, and agent registration
├── app/
│   ├── config.py         # Configuration (HOST, PORT, BRIDGE_CONFIG_DIR)
│   ├── lifespan.py       # Lifecycle context manager
│   ├── registry.py       # Module auto-registration logic
│   └── bridge_manager.py # External bridge management (init and close)
└── templates/
    ├── Dockerfile
    ├── pyproject.toml
    ├── main.py
    └── app/              # Sample project scaffold
        ├── config.py
        ├── mcp_server_configs/sample_slack.json
        ├── prompts/sample_prompt.py
        ├── resources/sample_echo_resource.py
        └── tools/sample_math_tools.py

pyproject.toml
README.md
```

### Writing Custom Modules

Register your own tools, resources and prompts using the provided decorators:

```python
from fastmcp import FastMCP
from viyv_mcp import tool, resource, prompt

def register(mcp: FastMCP):
    @tool(description="Add two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    @resource("echo://{message}")
    def echo_resource(message: str) -> str:
        return f"Echo: {message}"

    @prompt()
    def sample_prompt(query: str) -> str:
        return f"Your query is: {query}"
```

### Integrating with Slack and OpenAI Agents

The template project includes sample entries and agent definitions that show how to:

- Mount a Slack endpoint using `SlackAdapter` for handling Slack events.
- Define async functions with `@agent` and call them via HTTP or from other tools.
- Convert registered FastMCP tools into OpenAI Agents SDK functions with `build_function_tools`.

For example:

```python
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools

@agent(name="slack_agent", use_tags=["slack"])
async def slack_agent(action_japanese: str, instruction: str) -> str:
    oa_tools = build_function_tools(use_tags=["slack"])
    # ... implement agent logic here ...
```

Samples under `app/agents` and `app/entries` serve as a starting point for your own integrations.

### Slack Adapter Example

Mount a Slack endpoint using the bundled adapter:

```python
from fastapi import FastAPI
from viyv_mcp.app.adapters.slack_adapter import SlackAdapter
from viyv_mcp.run_context import RunContext

app = FastAPI()
adapter = SlackAdapter(
    bot_token="xoxb-***",
    signing_secret="your-signing-secret",
    context_cls=RunContext,
)
app.mount("/slack", adapter.as_fastapi_app())
```

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue or create a pull request on GitHub.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contact

For any inquiries, please contact:
- hiroki takezawa  
  Email: hiroki.takezawa@brainfiber.net
- GitHub: BrainFiber/viyv_mcp
