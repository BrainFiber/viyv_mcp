# viyv_mcp

**viyv_mcp** is a lightweight Python wrapper around [FastMCP](https://github.com/jlowin/fastmcp) and [Starlette](https://www.starlette.io/) that simplifies creating MCP (Model Context Protocol) servers with minimal boilerplate.

[![PyPI version](https://badge.fury.io/py/viyv_mcp.svg)](https://badge.fury.io/py/viyv_mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Quick Start

```bash
# Install the package
pip install viyv_mcp

# Create a new MCP server project
create-viyv-mcp new my_mcp_server

# Navigate to the project and install dependencies
cd my_mcp_server
uv sync

# Run the server
uv run python main.py
```

Your MCP server is now running at `http://localhost:8000` 🎉

## Overview

viyv_mcp provides:

- **CLI Tool**: Generate production-ready MCP server projects instantly
- **Decorator APIs**: Register tools, resources, prompts, and agents with simple decorators
- **Auto-registration**: Automatically discover and register modules in your project
- **External MCP Bridge**: Connect and manage external MCP servers seamlessly
- **Built-in Adapters**: Ready-to-use integrations for Slack and OpenAI Agents
- **Hot Reloading**: Dynamic tool injection keeps your agents up-to-date

## ✨ Key Features

### 🛠️ Simple Tool Creation
```python
from viyv_mcp import tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b
```

### 🤖 Agent Support
```python
from viyv_mcp import agent

@agent(name="calculator", use_tools=["add", "subtract"])
async def calculator_agent(query: str) -> str:
    # Your agent logic here
    pass
```

### 🌉 External MCP Server Bridge
```json
// app/mcp_server_configs/playwright.json
{
  "name": "playwright",
  "command": "npx",
  "args": ["@playwright/mcp@latest"]
}
```

### 🔗 Multiple Integration Options
- **Slack**: Built-in adapter for Slack bots and event handling
- **OpenAI Agents**: Bridge MCP tools to OpenAI function calling
- **Custom Endpoints**: Mount additional FastAPI apps with `@entry`

## 📦 Installation

```bash
pip install viyv_mcp
```

## 📁 Project Structure

When you create a new project with `create-viyv-mcp new my_project`, you get:

```
my_project/
├── main.py                # Server entry point
├── pyproject.toml         # Project dependencies (managed by uv)
├── Dockerfile             # Container deployment ready
└── app/
    ├── config.py          # Environment configuration
    ├── tools/             # Your MCP tools (@tool decorator)
    ├── resources/         # MCP resources (@resource decorator)
    ├── prompts/           # MCP prompts (@prompt decorator)
    ├── agents/            # AI agents (@agent decorator)
    ├── entries/           # Custom HTTP endpoints (@entry decorator)
    └── mcp_server_configs/ # External MCP server configurations
```

## 💻 Usage Examples

### Creating Custom Tools

Create a file `app/tools/my_tools.py`:

```python
from viyv_mcp import tool
from typing import Annotated
from pydantic import Field

def register(mcp):
    @tool(description="Calculate the area of a rectangle")
    def calculate_area(
        width: Annotated[float, Field(description="Width of the rectangle")],
        height: Annotated[float, Field(description="Height of the rectangle")]
    ) -> float:
        """Returns the area of a rectangle"""
        return width * height
```

### Creating Resources

Create a file `app/resources/my_resources.py`:

```python
from viyv_mcp import resource

def register(mcp):
    @resource("config://{key}")
    def get_config(key: str) -> str:
        """Retrieve configuration values"""
        configs = {
            "api_version": "1.0",
            "max_retries": "3"
        }
        return configs.get(key, "Not found")
```

### Creating an Agent

Create a file `app/agents/my_agent.py`:

```python
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools

@agent(name="math_agent", use_tools=["calculate_area", "add"])
async def math_agent(task: str) -> str:
    """An agent that can perform mathematical calculations"""
    # Get available tools
    tools = build_function_tools(use_tools=["calculate_area", "add"])
    
    # Your agent logic here
    return f"Completed task: {task}"
```

### Bridging External MCP Servers

Add a JSON config file in `app/mcp_server_configs/`:

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["@modelcontextprotocol/server-filesystem", "/path/to/workspace"],
  "env": {}
}
```

The external server's tools will be automatically available in your MCP server!

### Slack Integration

Create a file `app/entries/slack_entry.py`:

```python
from viyv_mcp import entry
from viyv_mcp.app.adapters.slack_adapter import SlackAdapter
from viyv_mcp.run_context import RunContext

@entry("/slack")
def create_slack_app():
    adapter = SlackAdapter(
        bot_token="xoxb-your-bot-token",
        signing_secret="your-signing-secret",
        context_cls=RunContext,
    )
    return adapter.as_fastapi_app()
```

### Custom API Endpoints

Create a file `app/entries/api.py`:

```python
from viyv_mcp import entry
from fastapi import FastAPI

@entry("/api/v1")
def create_api():
    app = FastAPI()
    
    @app.get("/status")
    def get_status():
        return {"status": "operational", "version": "1.0"}
    
    return app
```

## 🔧 Configuration

Environment variables you can set:

- `HOST`: Server host (default: `127.0.0.1`)
- `PORT`: Server port (default: `8000`)
- `BRIDGE_CONFIG_DIR`: Directory for external MCP configs (default: `app/mcp_server_configs`)
- `STATIC_DIR`: Static files directory (default: `static/images`)

## 🏗️ Advanced Features

### Auto-registration
All modules in `app/tools/`, `app/resources/`, `app/prompts/`, and `app/agents/` are automatically registered if they have a `register(mcp)` function.

### Dynamic Tool Injection
Tools are dynamically injected into agents on each request, ensuring they always have access to the latest available tools.

### Session Context
Tools can access session context (e.g., Slack events) through the `RunContextWrapper` parameter.

## 📚 Examples

Check out the `example/` directory for complete working examples:

- **claude_code_mcp**: MCP server that exposes Claude Code CLI functionality
- **test**: Comprehensive example with Slack integration and various agents

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/BrainFiber/viyv_mcp
cd viyv_mcp

# Install in development mode
pip install -e .

# Run tests
pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Hiroki Takezawa** - [BrainFiber](https://github.com/BrainFiber)

## 🙏 Acknowledgments

- Built on top of [FastMCP](https://github.com/jlowin/fastmcp) by jlowin
- Uses [Starlette](https://www.starlette.io/) for ASGI framework
- Inspired by the [Model Context Protocol](https://modelcontextprotocol.io/) specification

## 📮 Support

- 📧 Email: hiroki.takezawa@brainfiber.net
- 🐛 Issues: [GitHub Issues](https://github.com/BrainFiber/viyv_mcp/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/BrainFiber/viyv_mcp/discussions)
