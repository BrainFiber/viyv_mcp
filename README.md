# viyv_mcp

**viyv_mcp** is a production-ready Python wrapper around [FastMCP](https://github.com/jlowin/fastmcp) and [Starlette](https://www.starlette.io/) that simplifies creating MCP (Model Context Protocol) servers with minimal boilerplate.

[![PyPI version](https://badge.fury.io/py/viyv_mcp.svg)](https://badge.fury.io/py/viyv_mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.1.10-green.svg)](https://pypi.org/project/viyv_mcp/)

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

## ✨ Key Features

### 🛠️ Simple Tool Creation
```python
from viyv_mcp import tool

@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b
```

### 🤖 Agent Support with OpenAI Integration
```python
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools

@agent(name="calculator", use_tools=["add", "subtract"])
async def calculator_agent(query: str) -> str:
    tools = build_function_tools(use_tools=["add", "subtract"])
    # Agent implementation using OpenAI SDK
    return f"Result: {result}"
```

### 🌉 External MCP Server Bridge
```json
// app/mcp_server_configs/filesystem.json
{
  "command": "npx",
  "args": ["@modelcontextprotocol/server-filesystem", "/workspace"],
  "env": {
    "API_KEY": "$API_KEY"  // Environment variable interpolation
  },
  "cwd": "/path/to/working/dir",  // Optional
  "tags": ["filesystem", "io"]     // Optional: for filtering
}
```

### 🚀 Production-Ready Multi-Worker Support (New in v0.1.10)
```bash
# Enable stateless HTTP mode for multi-worker deployments
STATELESS_HTTP=true uv run python main.py

# Deploy with Gunicorn (recommended for production)
uv pip install gunicorn
STATELESS_HTTP=true uv run gunicorn main:app \
  -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 🔗 Built-in Integrations
- **Slack**: Full event handling, file management, thread context
- **OpenAI Agents SDK**: Seamless function calling bridge
- **ChatGPT**: Compatible with required `search`/`fetch` tools
- **Custom FastAPI Endpoints**: Mount additional APIs with `@entry`

## 📦 Installation

```bash
# Basic installation
pip install viyv_mcp

# With all optional dependencies
pip install "viyv_mcp[slack,openai]"
```

## 📁 Project Structure

When you create a new project with `create-viyv-mcp new my_project`:

```
my_project/
├── main.py                # Server entry point
├── pyproject.toml         # Dependencies (managed by uv)
├── Dockerfile             # Production-ready container
├── .env                   # Environment variables
└── app/
    ├── config.py          # Configuration management
    ├── tools/             # MCP tools (@tool decorator)
    ├── resources/         # MCP resources (@resource decorator)
    ├── prompts/           # MCP prompts (@prompt decorator)
    ├── agents/            # AI agents (@agent decorator)
    ├── entries/           # Custom HTTP endpoints (@entry decorator)
    └── mcp_server_configs/ # External MCP server configurations
```

## 💻 Advanced Usage Examples

### Tools with Runtime Context (Slack Integration)

```python
from viyv_mcp import tool
from viyv_mcp.run_context import RunContext
from agents import RunContextWrapper

def register(mcp):
    @tool(description="Get user info from context")
    def get_user_info(
        wrapper: RunContextWrapper[RunContext],
        user_id: str
    ) -> dict:
        """Get user information from Slack context"""
        context = wrapper.context
        if context and hasattr(context, 'slack_event'):
            # Access Slack event data
            return {"user": context.slack_event.get("user"), "channel": context.channel}
        return {"user": user_id, "source": "direct"}
```

### Creating Resources with URI Templates

```python
from viyv_mcp import resource

def register(mcp):
    @resource("database://{table}/{id}")
    def get_record(table: str, id: str) -> dict:
        """Fetch a database record by table and ID"""
        # Your database logic here
        return {"table": table, "id": id, "data": "..."}
```

### Prompts with Parameters

```python
from viyv_mcp import prompt
from typing import Annotated
from pydantic import Field

def register(mcp):
    @prompt("code_review")
    def code_review_prompt(
        language: Annotated[str, Field(description="Programming language")],
        code: Annotated[str, Field(description="Code to review")]
    ) -> str:
        return f"""
        Please review this {language} code:
        ```{language}
        {code}
        ```
        Focus on: performance, security, and best practices.
        """
```

### Slack Bot with File Handling

```python
from viyv_mcp import entry
from viyv_mcp.app.adapters.slack_adapter import SlackAdapter
from viyv_mcp.run_context import RunContext

@entry("/slack")
def create_slack_app():
    adapter = SlackAdapter(
        bot_token=os.getenv("SLACK_BOT_TOKEN"),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        context_cls=RunContext,
        handle_files=True,  # Enable file upload/download
        build_thread_history=True,  # Include thread context
    )
    return adapter.as_fastapi_app()
```

### ChatGPT-Compatible Tools

```python
from viyv_mcp import tool

def register(mcp):
    # Required for ChatGPT integration
    @tool(description="Search for information")
    def search(query: str) -> list:
        """Search tool required by ChatGPT"""
        results = perform_search(query)
        return [{"resource_link": f"resource://{r.id}", "title": r.title} for r in results]

    @tool(description="Fetch resource by ID")
    def fetch(id: str) -> dict:
        """Fetch tool required by ChatGPT (note: 'id' not 'uri')"""
        return get_resource_by_id(id)
```

## 🔧 Configuration

### Environment Variables

```bash
# Server Configuration
HOST=0.0.0.0                    # Server host (default: 127.0.0.1)
PORT=8000                        # Server port (default: 8000)
STATELESS_HTTP=true              # Enable stateless mode for multi-worker

# Directory Configuration
BRIDGE_CONFIG_DIR=app/mcp_server_configs  # External MCP configs
STATIC_DIR=static/images                  # Static file serving

# Integration Keys (optional)
SLACK_BOT_TOKEN=xoxb-...        # Slack bot token
SLACK_SIGNING_SECRET=...        # Slack signing secret
OPENAI_API_KEY=sk-...           # OpenAI API key
```

### Configuration Class

```python
# app/config.py
from viyv_mcp.app.config import Config

class MyConfig(Config):
    # Inherit base configuration

    @staticmethod
    def get_stateless_http():
        """Get stateless HTTP setting from environment"""
        env_val = os.getenv("STATELESS_HTTP", "").lower()
        if env_val in ("true", "1", "yes", "on"):
            return True
        elif env_val in ("false", "0", "no", "off"):
            return False
        return None  # Use FastMCP default
```

## 🏗️ Architecture & Advanced Features

### ASGI-Level Routing (SSE Streaming Fix)
viyv_mcp implements custom ASGI routing to fix SSE streaming issues:
- Direct `/mcp` path routing bypasses Starlette middleware
- Ensures proper Server-Sent Events handling
- Compatible with FastMCP's streaming protocol

### Dynamic Tool Injection
- Tools are refreshed on every request
- Agents always have access to the latest tools
- Supports runtime tool filtering with tags

### RunContextWrapper Pattern
- Signature manipulation for dual compatibility
- Works with both FastMCP and OpenAI Agents SDK
- Provides access to runtime context (Slack events, user info)

### External MCP Server Management
- Child process management with stdio communication
- Automatic tool/resource/prompt registration
- Environment variable interpolation in configs
- Tag-based filtering for selective tool inclusion

### Production Deployment Features

#### Stateless HTTP Mode
- No session ID requirements
- Perfect for load-balanced environments
- Enable with `STATELESS_HTTP=true`

#### Multi-Worker Deployment
```python
# test_app.py - Create a module for Gunicorn
from viyv_mcp import ViyvMCP
from app.config import Config

stateless_http = Config.get_stateless_http()
app = ViyvMCP("Production Server", stateless_http=stateless_http).get_app()
```

```bash
# Run with Gunicorn
gunicorn test_app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

#### Docker Deployment
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
CMD ["uv", "run", "gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

## 📊 Performance Optimization

### Caching Strategies
- Tools are cached per request
- External MCP connections are persistent
- Static file serving with efficient caching headers

### Resource Management
- Automatic cleanup of external MCP processes
- Connection pooling for external services
- Graceful shutdown handling

### Monitoring & Debugging
```bash
# Enable debug logging
LOG_LEVEL=DEBUG uv run python main.py

# Health check endpoint
curl http://localhost:8000/health
```

## 🔍 Troubleshooting

### Common Issues

#### SSE Streaming Not Working
- Ensure no middleware interferes with `/mcp` path
- Check ASGI routing configuration
- Verify FastMCP version >= 2.12.3

#### Multi-Worker Startup Failures
- Enable `STATELESS_HTTP=true` for multi-worker mode
- Use Gunicorn instead of uvicorn's `--workers` flag
- Check for asyncio event loop conflicts

#### External MCP Server Issues
```bash
# Check external server logs
tail -f logs/external_mcp.log

# Verify command exists
which npx

# Test configuration
cat app/mcp_server_configs/test.json | jq .
```

#### Protocol Compatibility
- Use MCP protocol version 2024-11-05
- Pydantic v2 compatibility is patched automatically
- Check `mcp_initialize_fix.py` for validation patches

## 📚 Examples

Complete working examples in the `example/` directory:

- **`claude_code_mcp`**: Claude Code CLI integration
- **`test`**: Comprehensive example with all features
  - Slack integration
  - OpenAI Agents
  - External MCP servers
  - Custom endpoints

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md).

### Development Setup

```bash
# Clone the repository
git clone https://github.com/BrainFiber/viyv_mcp
cd viyv_mcp

# Install in development mode
pip install -e .

# Run tests
pytest

# Build package
python -m build

# Run example project
cd example/test
uv sync
STATELESS_HTTP=true uv run python main.py
```

### Testing Guidelines
- Add sample implementations in `test/` directory
- Test with both session and stateless modes
- Verify Slack and OpenAI integrations
- Check external MCP server bridging

## 📄 License

MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Hiroki Takezawa** - [BrainFiber](https://github.com/BrainFiber)

## 🙏 Acknowledgments

- Built on [FastMCP](https://github.com/jlowin/fastmcp) by jlowin
- Powered by [Starlette](https://www.starlette.io/) ASGI framework
- Implements [Model Context Protocol](https://modelcontextprotocol.io/) specification
- Slack integration via [Slack Bolt](https://slack.dev/bolt-python/)
- OpenAI integration via [OpenAI Agents SDK](https://github.com/openai/agents-sdk)

## 📮 Support

- 📧 Email: hiroki.takezawa@brainfiber.net
- 🐛 Issues: [GitHub Issues](https://github.com/BrainFiber/viyv_mcp/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/BrainFiber/viyv_mcp/discussions)
- 📖 Documentation: [Wiki](https://github.com/BrainFiber/viyv_mcp/wiki)

## 🚦 Roadmap

- [ ] WebSocket support for real-time communication
- [ ] Built-in authentication/authorization
- [ ] Tool versioning and migration support
- [ ] Performance profiling dashboard
- [ ] Plugin system for custom integrations
- [ ] GraphQL endpoint support

## 📈 Changelog

### v0.1.10 (Latest)
- ✨ Added stateless HTTP support for multi-worker deployments
- 🔧 Improved ASGI-level routing for SSE streaming
- 📦 Updated FastMCP to 2.12.3 for better compatibility
- 🐛 Fixed Pydantic v2 validation issues
- 📚 Enhanced documentation and examples

### v0.1.9
- 🌉 External MCP server bridging with tags and filtering
- 🔄 Dynamic tool refresh on every request
- 📝 RunContextWrapper pattern for dual compatibility

### v0.1.8
- 🤖 OpenAI Agents SDK integration
- 💬 Slack adapter with file handling
- 🎯 ChatGPT-compatible tool requirements

---

Made with ❤️ by the viyv_mcp community