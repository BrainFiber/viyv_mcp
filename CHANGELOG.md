# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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