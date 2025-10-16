# Project Structure

## Root Directory Structure

```
viyv_mcp/
├── viyv_mcp/              # Main package directory
├── example/               # Example projects
├── test/                  # Test directory (sample implementations)
├── tests/                 # Unit tests (if any)
├── dist/                  # Build artifacts (generated)
├── tmp/                   # Temporary files (gitignored)
├── static/                # Static files
├── .serena/               # Serena memory files
├── .claude/               # Claude Code configuration
├── .vscode/               # VS Code settings
├── .git/                  # Git repository
├── .venv/                 # Virtual environment (gitignored)
├── pyproject.toml         # Package configuration
├── uv.lock                # UV lock file (gitignored)
├── README.md              # Main documentation
├── CLAUDE.md              # Claude Code instructions
├── CHANGELOG.md           # Version history
├── RELEASE_CHECKLIST.md   # Release procedures
├── AGENTS.md              # Agent development notes
├── LICENSE                # MIT License
├── .gitignore             # Git ignore rules
└── .python-version        # Python version specification
```

## Package Directory (viyv_mcp/)

### Core Files
```
viyv_mcp/
├── __init__.py            # Package exports (ViyvMCP, decorators, version)
├── core.py                # Main ViyvMCP class with ASGI routing
├── decorators.py          # @tool, @resource, @prompt, @agent, @entry
├── cli.py                 # create-viyv-mcp CLI tool
├── openai_bridge.py       # OpenAI Agents SDK integration
├── agent_runtime.py       # Agent runtime utilities
├── run_context.py         # RunContext and RunContextWrapper
├── _version.py            # Version information
└── pyproject.toml         # Package metadata
```

### App Components (viyv_mcp/app/)
```
viyv_mcp/app/
├── __init__.py
├── config.py              # Configuration management (HOST, PORT, etc.)
├── registry.py            # Auto-registration of modules
├── bridge_manager.py      # External MCP server management
├── entry_registry.py      # Registry for FastAPI app entries
├── lifespan.py            # Application lifespan management
├── logging_config.py      # Logging configuration
├── mcp_initialize_fix.py  # Pydantic v2 compatibility patches
├── request_interceptor.py # Request interception utilities
└── adapters/
    └── slack_adapter.py   # Slack event handling and integration
```

### Middleware (viyv_mcp/middleware/)
```
viyv_mcp/middleware/
└── [middleware components]
```

### MCP Components (viyv_mcp/mcp/)
```
viyv_mcp/mcp/
└── [MCP-specific components]
```

### Storage (viyv_mcp/storage/)
```
viyv_mcp/storage/
└── [storage-related components]
```

### Templates (viyv_mcp/templates/)
Project generation templates used by `create-viyv-mcp`:

```
viyv_mcp/templates/
├── main.py                # Template for main.py
├── pyproject.toml         # Template for pyproject.toml
├── Dockerfile             # Template for Docker deployment
├── .env                   # Template for environment variables
└── app/
    ├── config.py          # Template for app configuration
    ├── tools/
    │   └── sample_math_tools.py
    ├── resources/
    │   └── sample_echo_resource.py
    ├── prompts/
    │   └── sample_prompt.py
    ├── agents/
    │   ├── sample_calc_agent.py
    │   ├── sample_slack_agent.py
    │   ├── sample_slack_response_agent.py
    │   ├── sample_think_agent.py
    │   └── sample_notion_agent.py
    ├── entries/
    │   ├── sample_health.py
    │   ├── sample_webhook.py
    │   └── sample_slack.py
    └── mcp_server_configs/
        └── [External MCP server JSON configs]
```

## Generated Project Structure

When you run `create-viyv-mcp new my_project`:

```
my_project/
├── main.py                # Server entry point
├── test_app.py            # Gunicorn entry point (for multi-worker)
├── pyproject.toml         # Dependencies (managed by uv)
├── uv.lock                # UV lock file
├── Dockerfile             # Production-ready container
├── .env                   # Environment variables (gitignored)
└── app/
    ├── config.py          # Configuration class
    ├── tools/             # MCP tools (@tool decorator)
    │   └── sample_math_tools.py
    ├── resources/         # MCP resources (@resource decorator)
    │   └── sample_echo_resource.py
    ├── prompts/           # MCP prompts (@prompt decorator)
    │   └── sample_prompt.py
    ├── agents/            # AI agents (@agent decorator)
    │   ├── sample_calc_agent.py
    │   ├── sample_slack_agent.py
    │   └── sample_think_agent.py
    ├── entries/           # Custom HTTP endpoints (@entry decorator)
    │   ├── sample_health.py
    │   ├── sample_webhook.py
    │   └── sample_slack.py
    └── mcp_server_configs/ # External MCP server configurations (JSON)
        └── [your_server.json]
```

## Example Projects

### example/test/
Comprehensive test project with all features:
```
example/test/
├── main.py                # Server entry point
├── test_app.py            # Multi-worker entry point
├── pyproject.toml         # Dependencies
├── .env                   # Environment variables
├── Dockerfile             # Container definition
├── test_mcp_client.py     # MCP client tests
├── test_mcp_correct_client.py
├── test_mcp_init.py
└── app/
    ├── config.py
    ├── tools/
    ├── resources/
    ├── prompts/
    ├── agents/
    ├── entries/
    └── mcp_server_configs/
```

### example/claude_code_mcp/
Claude Code CLI integration example:
```
example/claude_code_mcp/
├── main.py
├── setup.sh              # Setup script
└── app/
    └── [similar structure]
```

## Key Directories Explained

### `/viyv_mcp` - Core Package
Contains all the framework code. This is what gets published to PyPI.

### `/example` - Example Projects
Working examples demonstrating various features. Use these as reference implementations.

### `/test` - Test Directory
Contains sample implementations rather than unit tests. Run `uv run python main.py` to test.

### `/tmp`, `/scratch`, `/.tmp` - Temporary Files
**GITIGNORED** - Use these for temporary scripts and experiments that can be deleted anytime.

### `/static` - Static Files
Static file serving directory. Default path: `static/images`

### `/.serena` - Serena Memory
Memory files created by Serena agent for project knowledge.

### `/.claude` - Claude Code Config
Claude Code specific configuration and slash commands.

## File Placement Guidelines

### Where to Place New Files

#### Permanent Scripts
- Development scripts → `scripts/` directory (create if needed)
- Test utilities → `test/utils/` directory
- Build automation → `scripts/build/`

#### Temporary Files
- Quick experiments → `tmp/` (gitignored)
- Scratch work → `scratch/` (gitignored)
- Hidden temps → `.tmp/` (gitignored)

#### Never Place Files In
- Root directory (unless it's a config file)
- Inside `viyv_mcp/` package (unless adding features)
- Random subdirectories without clear purpose

## Important File Locations

### Configuration Files
- `pyproject.toml` - Package metadata and dependencies
- `.env` - Environment variables (NEVER commit!)
- `.gitignore` - Git ignore rules
- `.python-version` - Python version (3.12.7 for this project)

### Documentation Files
- `README.md` - User-facing documentation
- `CLAUDE.md` - Claude Code development guide
- `CHANGELOG.md` - Version history
- `RELEASE_CHECKLIST.md` - Release procedures
- `AGENTS.md` - Agent development notes

### Build Artifacts (Generated, Gitignored)
- `dist/` - Built packages (.whl, .tar.gz)
- `build/` - Build intermediate files
- `*.egg-info/` - Package metadata
- `__pycache__/` - Python bytecode
- `.pytest_cache/` - Pytest cache

## Module Auto-Registration

The framework auto-imports modules from these directories:
1. `app/tools/` - Tool modules
2. `app/resources/` - Resource modules
3. `app/prompts/` - Prompt modules
4. `app/agents/` - Agent modules
5. `app/entries/` - Entry point modules

Each module must define: `def register(mcp: FastMCP):`

## External MCP Server Configs

JSON files in `app/mcp_server_configs/`:
- Each file defines one external MCP server
- Must have `.json` extension
- Loaded automatically on startup
- Tools/resources/prompts bridged to main server

## Static Files

Default location: `static/images/`
- Configurable via `STATIC_DIR` environment variable
- Used for image uploads, file serving, etc.
- Example: Slack adapter uploads go here
