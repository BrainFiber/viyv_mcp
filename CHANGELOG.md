# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-03-28

### Fixed
- **Capabilities: conditional prompts/resources** — `prompts` and `resources` capabilities are now only advertised when at least one prompt/resource is actually registered. Previously, empty capabilities caused Agent SDK to call `list_resources` → `Method not found` error, breaking ToolSearch index

## [2.0.0] - 2026-03-27

### Changed (Architecture)
- **FastMCP removed**: Replaced with direct `mcp` SDK v1.26.0 (`mcp.server.lowlevel.Server`). Eliminates non-standard `extensions` field in capabilities that broke Claude Agent SDK compatibility
- **New `McpServer` class** (`viyv_mcp/server/mcp_server.py`): Owns tool/resource/prompt registry, handles MCP protocol, provides stdio and StreamableHTTP transports
- **New `McpRegistry`** (`viyv_mcp/server/registry.py`): Unified registry with integrated security metadata (replaces separate `ToolSecurityRegistry`)
- **Security integrated at handler level**: Namespace filtering and clearance checks in `list_tools`/`call_tool` handlers instead of FastMCP middleware
- **Bridge manager simplified**: ~80 lines of signature construction code removed. JSON Schema passed directly to `McpServer.register_tool()`
- **`@entry` simplified**: Removed `use_tools`/`exclude_tools`/`use_tags`/`exclude_tags` parameters (MCP server responsibility is tool exposure, not internal routing)
- **`@tool` annotations**: `title` and `destructive` parameters now map to MCP `ToolAnnotations`

### Added
- `viyv_mcp/server/` package — `McpServer`, `McpRegistry`, `ToolEntry`, `ResourceEntry`, `PromptEntry`
- `ToolMetadataProvider` Protocol in `security/domain/models.py` for dependency inversion
- `_ensure_async()` helper for sync→async tool wrapping
- `_build_input_schema()` — generates JSON Schema from Python type hints via pydantic

### Removed
- **`fastmcp` dependency** — replaced by `mcp>=1.26.0`
- **`@agent` decorator** — internal tool-calling-tools mechanism is not MCP server responsibility
- **`agent_runtime.py`** module — ContextVar tool injection infrastructure
- **`_collect_tools_map()`**, **`_wrap_callable_with_tools()`**, **`_wrap_factory_with_tools()`** — internal agent framework code
- **`_tool_fn_registry`** — no longer needed without agent tool collection
- **Observer pattern** (`_fire_tool_event`, `add_tool_event_hook`) — security metadata stored directly in `ToolEntry`
- **`ToolSecurityRegistry`** (`security/tool_registry.py`) — merged into `McpRegistry`
- **`ViyvSecurityMiddleware`** (`security/fastmcp_middleware.py`) — security checks moved to McpServer handlers

### Fixed
- **Agent SDK compatibility**: `capabilities` response no longer includes non-standard `extensions: {"io.modelcontextprotocol/ui": {}}` field
- **`serverInfo.version`** now shows viyv_mcp version instead of FastMCP version
- **Test event loop errors**: Replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()`

## [1.1.0] - 2026-03-27

### Changed
- **Security: numeric clearance/security_level**: Both values are now integers (0 = highest privilege). String-based labels and `DEFAULT_SECURITY_LEVELS` mapping removed
- **Access rule**: `jwt.clearance <= tool.security_level` grants access (lower number = higher privilege)
- **Missing values**: No clearance in JWT → lowest privilege (denied if tool has restriction); No security_level on tool → unrestricted (anyone can access)
- **CLI**: `--clearance` now accepts an integer and is optional (omit for lowest privilege)
- **Bridge config**: `security_level` and `security_level_map` now use integer values
- **Backward compatibility**: Legacy string clearance/security_level values produce a warning and are treated as undefined (graceful degradation)

### Removed
- `DEFAULT_SECURITY_LEVELS` constant (string-to-rank mapping no longer needed)
- `SecurityLevel` dataclass (unused)
- `resolve_security_level_rank()` function (replaced by direct numeric comparison)
- `SecurityConfig.security_levels` field (label mapping no longer needed)

## [1.0.1] - 2026-03-27

### Fixed
- **HTTP lifespan not initialized with security**: `compose_lifespan` now receives explicit lifespan callables instead of extracting from ASGI apps (which fails after security wrapping)
- **`init_bridges` single-file support**: Accepts both a directory path and a single JSON file path

### Added
- **`ViyvMCP.run_stdio_async()`**: Complete stdio transport entry point with bridge lifecycle management and security middleware support
- **`python -m viyv_mcp serve` CLI**: Start MCP server without a project directory — bridges external servers via `--bridges` flag (stdio default, `--http` for HTTP mode)
- **`ViyvMCP(bridge_config=...)` parameter**: Override bridge config path (file or directory)

## [1.0.0] - 2026-03-27

### Changed (Architecture)
- **core.py decomposed**: God Object split into 3 focused modules
  - `app/mcp_factory.py` — FastMCP creation + module auto-registration
  - `app/asgi_builder.py` — WS bridge setup, security layer, route assembly
  - `app/lifespan_composer.py` — composite lifespan management
  - `core.py` reduced to thin ASGI facade (251→149 lines)
- **decorators.py simplified**: Removed RunContextWrapper dead code (583→461 lines)
  - Removed dual-function pattern (impl + _schema_stub) → single registration
  - Removed v2 fallback path in `_collect_tools_map`
  - `_wrap_callable_with_tools()` now only handles tools ContextVar injection
- **bridge_manager.py hardened**: AsyncExitStack + timeout for safe process management
  - 30s startup timeout, 10s shutdown timeout via `asyncio.wait_for`
  - Per-bridge failure isolation (one failure doesn't affect others)
  - Proper resource cleanup on partial initialization failure

### Fixed
- **Security initialization silent failure**: Previously, if security layer init failed, server ran unprotected with only a debug log. Now: ImportError (module absent) is info-logged; other errors are raised to prevent unprotected startup
- **asyncio.run() bug in entry decorator**: `_wrap_factory_with_tools()` crashed with RuntimeError when called inside an already-running event loop
- **@agent decorator missing error handling**: Added try/except for `_get_mcp_from_stack()` (matching @entry pattern)
- **Security hook ImportError logged at wrong level**: Changed from debug to warning so production servers notice when tool metadata sync is broken

### Added
- **E2E architecture test suite**: 31 tests covering decorator registration, tool execution, security Observer, ViyvMCP assembly, new modules, bridge manager, MCP protocol compatibility
- **Error handling in tool registration**: `mcp.tool()` failures now logged and handled gracefully
- **_fire_tool_event() logging**: Hook failures now logged at warning level instead of silently swallowed
- **Defensive null checks**: WS bridge callbacks guard against missing relay MCP

### Removed
- **Slack Adapter** (`slack_adapter.py`): Moved out of core package. `slack-bolt` and `aiohttp` removed from hard dependencies (available as `pip install viyv_mcp[slack]`)
- **OpenAI Agents SDK Bridge** (`openai_bridge.py`): Moved out of core package. `openai-agents` removed from hard dependencies (available as `pip install viyv_mcp[openai]`)
- **RunContext** (`run_context.py`): Abstract base class removed (was only used by Slack Adapter)
- **RunContextWrapper handling**: All dead code removed from decorators.py (~150 lines)
- Slack/OpenAI-dependent template files and example agents

### Security
- **JWT Security Framework**: Complete authentication and authorization subsystem
  - `viyv_mcp/app/security/` — Clean Architecture (Domain / Infrastructure / Application / Interface)
  - FastMCP native middleware (`on_call_tool`, `on_list_tools`) works for both stdio and HTTP
  - ASGI JWT extractor middleware for HTTP `Authorization: Bearer` header
  - ContextVar-based identity bridge between transport layers
  - Observer pattern: `decorators.py` fires tool event hooks without depending on security package
- **Namespace Access Control**: `@tool(namespace="hr")` — agents see only tools in their trusted namespaces
- **Security Level Enforcement**: `@tool(security_level="confidential")` — clearance rank check
- **Bridge Security Metadata**: `namespace`, `security_level`, `namespace_map`, `security_level_map` fields in bridge JSON configs
- **Audit Logging**: Structured JSON audit log via Python logging (`viyv_mcp.security.audit`)
- **CLI**: `python -m viyv_mcp generate-jwt` — generate signed JWTs for agent authentication
- **Operating Modes**: bypass (dev), authenticated (JWT), deny_all (default safe)

## [0.1.21] - 2026-03-25

### Changed
- Separate relay MCP endpoint, fix tool parameter schemas

## [0.1.20] - 2026-03-24

### Fixed
- Fix WS Bridge double-wrap, screenshot ImageContent, tabId required

## [0.1.19] - 2026-03-23

### Added
- Add WebSocket bridge for Chrome extension relay

## [0.1.18] - 2026-03-22

### Changed
- Upgrade FastMCP 2.x → 3.1.0

## [0.1.17] - 2025-10-16

### Fixed
- **Version String Hotfix**: Updated `__version__` variable in `__init__.py` to correctly reflect 0.1.17
  - Previous release (0.1.16) had `__version__` still set to "0.1.14"
  - This hotfix ensures package version consistency

## [0.1.16] - 2025-10-16

### Fixed
- **Prompt Parameter Parsing Bug**: Fixed `_register_prompt_bridge()` in `bridge_manager.py` to correctly handle `PromptArgument` objects
  - Changed parameter parsing to access `PromptArgument` object attributes (`arg.name`, `arg.required`) instead of treating them as dictionaries
  - Fixed `ValueError: "name='account_ids' description=None required=True" is not a valid parameter name`
  - The `PromptArgument.required` field now properly controls parameter default values (True = required, False = optional with `default=None`)
  - All prompt parameters are treated as `str` type (MCP Protocol does not provide type information for prompt arguments)
  - AWS MCP servers with prompts (`awslabs.billing-cost-management-mcp-server`, etc.) now work correctly

### Added
- Added comprehensive test suite for prompt parameter parsing fix (`example/test/test_prompt_fix.py`)
  - Tests for required vs optional parameters
  - Tests for prompts with/without descriptions
  - Tests for default required behavior when `required=None`

### Changed
- Updated `_register_prompt_bridge()` docstrings with correct MCP Protocol specification details
- Improved parameter default handling based on `required` field

## [0.1.15] - 2025-10-16

### Fixed
- **AWS MCP Servers Compatibility**: Fixed `bridge_manager.py` to correctly parse MCP Protocol responses
  - Changed `_safe_list_resources()` to iterate over `ListResourcesResult.resources` instead of the result object itself
  - Changed `_safe_list_prompts()` to iterate over `ListPromptsResult.prompts` instead of the result object itself
  - Fixed ValidationErrors where `meta` and `nextCursor` fields were incorrectly treated as Resource/Prompt objects
  - AWS official MCP servers (`awslabs.billing-cost-management-mcp-server`, `awslabs.bedrock-kb-retrieval-mcp-server`) now work correctly

### Added
- Added `_get_resource_uri()` helper function for SDK version compatibility (supports both `uri` and `uriTemplate` attributes)
- Added pagination logging: logs when `nextCursor` is present in resources/prompts responses
- Added comprehensive test suite for bridge manager fixes (`example/test/test_bridge_fix.py`)
- Added example MCP server configuration files for AWS services

### Changed
- Updated resource and prompt logging to use URI compatibility helper
- Improved docstrings in `_safe_list_resources()` and `_safe_list_prompts()` with MCP Protocol specification details

## [0.1.6] - 2025-08-21

### Fixed
- Fixed Pydantic v2 compatibility issue in `openai_bridge.py`
  - Changed from Pydantic v1 style `type("Config", ...)` to v2 style `ConfigDict(...)`
  - Resolves `TypeError: 'type' object is not iterable` when using `build_function_tools()`
  - Affects all agents using OpenAI Agents SDK integration

## [0.1.5] - 2025-08-20

### Added
- Support for MCP protocol version 2025-06-18
- Enhanced error handling and validation

## [0.1.4] - 2025-06-23

### Added
- Export `entry` decorator in `__init__.py` for proper module imports
- Created comprehensive `claude_code_mcp` example demonstrating Claude Code CLI integration
- Added file placement guidelines in CLAUDE.md for temporary and permanent scripts

### Changed
- Improved `auto_register_modules` to gracefully handle missing optional directories (entries, resources, etc.)
  - Changed from ERROR to DEBUG logging for missing directories
  - This allows projects to only include the features they need without errors

### Fixed
- Fixed import error for `entry` decorator in generated projects
- Fixed module registration errors when optional directories don't exist

### Documentation
- Updated CLAUDE.md with:
  - Development installation command for example projects (`uv pip install -e ../../`)
  - File placement guidelines for scripts and temporary files
  - MCP tool development guidelines from AGENTS.md
  - Claude CLI integration notes
  - ChatGPT compatibility requirements

## [0.1.3] - Previous releases

### Added
- Initial release of viyv_mcp wrapper for FastMCP + Starlette
- Decorator-based APIs for tools, resources, prompts, and agents
- Auto-registration system for modules
- External MCP server bridge functionality
- Slack and OpenAI Agents integration adapters
- CLI tool `create-viyv-mcp` for project generation