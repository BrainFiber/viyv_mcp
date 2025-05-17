# Project Overview

`viyv_mcp` is a Python package that wraps **FastMCP** and **Starlette**. It lets you generate and run an MCP server with sample tools, resources and prompt definitions.

## Key Features
- CLI `create-viyv-mcp` generates a ready-to-run template project.
- Decorators `@tool`, `@resource`, `@prompt`, `@agent` simplify registration of modules.
- Automatically bridges external MCP servers via JSON config files under `app/mcp_server_configs`.
- Includes optional adapters for Slack and OpenAI Agents.
- Dynamic tool injection keeps tools up to date for entries and agents.

## Quick Start
1. Install the package from PyPI:
   ```bash
   pip install viyv_mcp
   ```
2. Create a new project template:
   ```bash
   create-viyv-mcp new my_mcp_project
   ```
3. Inside the generated directory run:
   ```bash
   uv sync
   uv run python main.py
   ```
The server starts on `0.0.0.0:8000` and automatically registers modules and bridges external servers defined in `app/mcp_server_configs`.

## Configuration
- `Config` (see `viyv_mcp/app/config.py`) exposes environment variables:
  - `HOST` (default `127.0.0.1`)
  - `PORT` (default `8000`)
  - `BRIDGE_CONFIG_DIR` (default `app/mcp_server_configs`)
- `STATIC_DIR` controls the directory for static files (`static/images` by default).

## Usage Notes
- `ViyvMCP` assembles an ASGI app combining Streamable HTTP, static files and custom entries. It mounts FastMCP at `/mcp` by default and handles startup/shutdown of external MCP bridges.
- External MCP servers are launched according to JSON files containing `command`, `args`, and optional environment variables. OS environment variables take precedence.
- Decorator `@entry(path)` registers additional FastAPI apps; `@agent` registers callable tools for OpenAI Agents via `build_function_tools`.
- The package is released under the MIT License.

