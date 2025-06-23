# Claude Code MCP Server Example

This example demonstrates how to expose Claude Code CLI functionality through an MCP (Model Context Protocol) server using `viyv_mcp`. It provides advanced session management and real-time stream processing for seamless Claude CLI integration.

## Overview

This MCP server provides comprehensive tools to interact with the Claude Code CLI, featuring:
- Execute Claude Code commands with full session support (`--resume`)
- Advanced session management with context preservation
- Real-time stream JSON output processing
- Session listing and deletion capabilities
- CLI availability and version checking

## Prerequisites

- Python 3.11+
- Claude CLI installed (`pip install claude-cli` or follow official installation guide)
- `uv` package manager

## Installation

```bash
# Run setup script (installs viyv_mcp in editable mode)
./setup.sh

# Or manually:
uv pip install -e ../../  # Install viyv_mcp from parent directory
uv sync                   # Install other dependencies
```

## Running the Server

```bash
# Start the MCP server
uv run python main.py
```

The server will start on `http://0.0.0.0:8000` by default.

## Available Tools

### 1. `claude_cli`
Execute Claude Code CLI commands with advanced session support.

**Parameters:**
- `prompt` (required): The prompt or task for Claude Code
- `context_id` (optional): Session ID for continuing conversation
  - Omit for new session
  - Use specific ID to continue session
  - Use "latest" for most recent session
- `cwd` (optional): Working directory (default: `app/claude_workspace/`)
- `max_turns` (optional): Maximum interaction turns (1-10, default: 3)

**Features:**
- Stream JSON output parsing for real-time feedback
- Automatic session persistence with `--resume` support
- Context preservation between calls
- Comprehensive error handling

**Example:**
```python
# New session
result = await claude_cli(prompt="Analyze example.py")

# Continue session
result = await claude_cli(
    prompt="Add type hints",
    context_id="cli_session_20250623_120000"
)

# Use latest session
result = await claude_cli(
    prompt="Now add tests",
    context_id="latest"
)
```

### 2. `list_claude_cli_sessions`
Display saved Claude CLI sessions with metadata.

**Parameters:**
- `limit` (optional): Number of sessions to display (1-50, default: 10)

**Example Response:**
```
=== Claude CLI Sessions ===

Context ID: cli_session_20250623_120000
  Last Updated: 2025-06-23T12:00:00
  Last Action: Analyze example.py...
  Messages: 5
```

### 3. `delete_claude_cli_session`
Remove a specific Claude CLI session.

**Parameters:**
- `context_id` (required): Session ID to delete

### 4. `claude_cli_version`
Check Claude CLI availability and version information.

## Session Management

Sessions are stored in `app/claude_cli_sessions.json` with comprehensive metadata:
- Session ID from Claude CLI
- Complete message history (stream JSON)
- Last action performed
- Timestamps and message counts

Session continuation modes:
- **New session**: Omit `context_id`
- **Specific session**: Provide exact `context_id`
- **Latest session**: Use `context_id="latest"`

## Environment Variables

- `HOST`: Server host (default: 127.0.0.1)
- `PORT`: Server port (default: 8000)

## Testing with MCP Client

You can test the server using any MCP client. Here's an example using curl:

```bash
# Health check
curl http://localhost:8000/health

# Execute Claude Code command via MCP
# (Requires proper MCP client implementation)
```

## Working Directory

The server includes a workspace at `app/claude_workspace/` with sample files:
- `test.txt` - Simple text file for testing
- `example.py` - Python code with fibonacci function

Claude CLI operates within this directory by default, or you can specify a custom working directory via the `cwd` parameter.

## Implementation Details

- **Stream Processing**: Parses Claude CLI's `--output-format stream-json` for real-time updates
- **Session Persistence**: Uses async file locks for thread-safe session management
- **Error Handling**: Comprehensive error messages and graceful degradation
- **Logging**: Detailed logging for debugging (check server logs)

## Notes

- Claude CLI must be installed: `npm install -g @anthropic-ai/claude-cli`
- Sessions persist across server restarts
- Default timeout is 5 minutes per Claude CLI execution
- All file operations are protected with async locks for thread safety

## Additional Resources

- See `app/tools/claude_cli_usage.md` for detailed usage guide
- Check logs for debugging information
- Example workflows included in documentation