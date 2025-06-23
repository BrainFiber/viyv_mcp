# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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