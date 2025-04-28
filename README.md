README.md

# viyv_mcp

**viyv_mcp** is a simple Python wrapper library for FastMCP and Starlette.  
It enables you to quickly create a fully‐configured MCP server project with sample tools, resources, prompts, and external configuration support.

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
- **Template Inclusion:**  
  The generated project templates include:
  - **Configuration Files:** (e.g. `app/config.py`)
  - **Prompts:** (e.g. `app/prompts/sample_prompt.py`)
  - **Resources:** (e.g. `app/resources/sample_echo_resource.py`)
  - **Tools:** (e.g. `app/tools/sample_math_tools.py`)
  - **MCP Server Configs:** (e.g. `app/mcp_server_configs/sample_slack.json`)
  - **Dockerfile**, **pyproject.toml**, and **main.py** for the generated project.

## Installation

### From PyPI

Install **viyv_mcp** via pip:

```bash
pip install viyv_mcp
```

This installs the package as well as provides the CLI command `create-viyv-mcp`.

## Usage

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

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue or create a pull request on GitHub.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contact

For any inquiries, please contact:
- hiroki takezawa  
  Email: hiroki.takezawa@brainfiber.net
- GitHub: BrainFiber/viyv_mcp
