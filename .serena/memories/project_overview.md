# Project Overview: viyv_mcp

## Purpose
**viyv_mcp** is a production-ready Python wrapper around FastMCP and Starlette that simplifies creating MCP (Model Context Protocol) servers with minimal boilerplate. It provides a decorator-based API for tools, resources, prompts, and agents, along with built-in adapters for Slack and OpenAI Agents integration.

## Key Information
- **Package Name**: viyv_mcp
- **Current Version**: 0.1.12 (pyproject.toml), 0.1.11 (__init__.py)
- **PyPI Published**: Yes (https://pypi.org/project/viyv_mcp/)
- **Repository**: https://github.com/BrainFiber/viyv_mcp
- **Python Version**: >= 3.10
- **License**: MIT

## Core Technologies
- **FastMCP** (>= 2.12.3) - MCP protocol implementation
- **Starlette** (>= 0.25.0) - ASGI framework
- **Uvicorn** (>= 0.22.0) - ASGI server
- **FastAPI** (>= 0.115.12) - Web framework for custom endpoints
- **Pydantic** (>= 2) - Data validation (v2 compatibility focus)
- **Slack Bolt** (>= 1.23.0) - Slack integration
- **OpenAI Agents** (>= 0.0.13) - OpenAI Agents SDK integration
- **pytest** (>= 7.0) - Testing framework
- **aiohttp** (>= 3.11.18) - Async HTTP client

## Main Features

### 1. Decorator-Based APIs
- `@tool` - Register MCP tools
- `@resource` - Register MCP resources
- `@prompt` - Register MCP prompts
- `@agent` - Register AI agents
- `@entry` - Mount custom FastAPI endpoints

### 2. Auto-Registration System
- Modules in `app/tools/`, `app/resources/`, etc. are automatically imported
- Each module defines a `register(mcp: FastMCP)` function
- Decorators automatically find the FastMCP instance from the call stack

### 3. External MCP Server Bridge
- JSON configs in `app/mcp_server_configs/` define external MCP servers
- Child processes managed automatically with stdio communication
- Environment variable interpolation supported
- Tag-based filtering for selective tool inclusion

### 4. Production Features
- **Stateless HTTP Mode** (v0.1.10+): Multi-worker support without session IDs
- **ASGI-Level Routing**: Custom routing for SSE streaming fix
- **Dynamic Tool Injection**: Tools refreshed on every request
- **RunContextWrapper Pattern**: Dual compatibility with FastMCP and OpenAI SDK

### 5. Built-in Integrations
- **Slack**: Full event handling, file management, thread context
- **OpenAI Agents SDK**: Function calling bridge with schema transformation
- **ChatGPT**: Compatible with required `search`/`fetch` tools
- **Custom Endpoints**: Mount additional FastAPI apps with `@entry`

## Architecture Highlights

### ASGI-Level Routing
- Custom ASGI routing sends `/mcp` paths directly to MCP app
- Bypasses Starlette middleware to fix SSE streaming issues
- Ensures proper Server-Sent Events handling

### Signature Manipulation
- RunContextWrapper parameter for agent execution
- Clean JSON Schema generation for FastMCP
- Works with both FastMCP and OpenAI Agents SDK

### MCP Protocol Support
- Protocol version: 2024-11-05
- Pydantic v2 compatibility patches in `mcp_initialize_fix.py`
- Handles initialize requests with proper validation

## CLI Tool
- **create-viyv-mcp**: Project generator CLI
- Creates new MCP server projects with complete structure
- Includes Dockerfile, .env template, sample tools/agents

## Use Cases
1. Quick MCP server creation with minimal code
2. Slack bot development with MCP tool integration
3. OpenAI Agents with custom function tools
4. Multi-worker production deployments
5. Bridging external MCP servers into unified API
