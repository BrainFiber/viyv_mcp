# Claude CLI Tool Usage Guide

## Overview

This MCP server provides tools to interact with Claude Code CLI, offering advanced session management for maintaining conversation context across multiple interactions.

## Session Management

The tool implements sophisticated session management to preserve conversation history using Claude CLI's `--resume` feature.

### Basic Usage Patterns

1. **New Session (no context_id)**
   ```
   claude_cli(prompt="Display test.txt")
   ```
   → A new session ID is automatically generated

2. **Continue Specific Session (with context_id)**
   ```
   claude_cli(
     prompt="Convert to Japanese", 
     context_id="cli_session_20250623_112814"
   )
   ```
   → Continues the specified session with preserved conversation history

3. **Use Latest Session**
   ```
   claude_cli(
     prompt="Continue please", 
     context_id="latest"
   )
   ```
   → Automatically uses the most recently active session

## Available Tools

### 1. `claude_cli`
Main tool for executing Claude Code CLI commands with session support.

**Parameters:**
- `prompt` (required): The task or question for Claude
- `context_id` (optional): Session identifier
  - Omit for new session
  - Use specific ID to continue session
  - Use "latest" for most recent session
- `cwd` (optional): Working directory (default: `app/claude_workspace/`)
- `max_turns` (optional): Maximum interaction turns (1-10, default: 3)

**Features:**
- Stream JSON output parsing for real-time feedback
- Automatic session ID extraction from CLI output
- Context preservation between calls
- Working directory management
- Comprehensive error handling

### 2. `list_claude_cli_sessions`
Displays available sessions with their metadata.

**Parameters:**
- `limit` (optional): Number of sessions to display (1-50, default: 10)

**Output includes:**
- Context ID (session identifier)
- Last update timestamp
- Last action performed
- Total message count

### 3. `delete_claude_cli_session`
Removes a specific session from storage.

**Parameters:**
- `context_id` (required): Session ID to delete

### 4. `claude_cli_version`
Checks Claude CLI availability and version.

## Session Storage

- Sessions are stored in `app/claude_cli_sessions.json`
- Each session contains:
  - Session ID from Claude CLI
  - Complete message history
  - Metadata (last action, timestamps)
  - Result summaries

## Working Directory

- Default: `app/claude_workspace/`
- Contains sample files for testing:
  - `test.txt` - Simple text file
  - `example.py` - Python code example
- Claude CLI operates within this directory by default

## Advanced Features

### Stream Processing
The tool processes Claude CLI's stream JSON output to provide:
- Real-time status updates
- Tool usage notifications
- Progress indicators
- Error messages

### Session Context
When resuming sessions, the tool:
- Loads previous conversation context
- Appends context hints to prompts
- Maintains conversation continuity

### Error Handling
- Graceful handling of missing Claude CLI
- Timeout protection (5 minutes default)
- Detailed error logging
- Session state preservation on errors

## Best Practices

1. **Session Management**
   - Use meaningful prompts for easy session identification
   - Regularly check session list to manage storage
   - Delete old sessions when no longer needed

2. **Performance**
   - Use appropriate `max_turns` values (3-5 recommended)
   - Provide clear, specific prompts
   - Use session continuation for related tasks

3. **Debugging**
   - Check logs for detailed execution information
   - Review session metadata for context
   - Use `claude_cli_version` to verify installation

## Example Workflows

### Example 1: File Analysis and Modification
```
# Step 1: Analyze a file
claude_cli(prompt="Analyze example.py and suggest improvements")
# Returns: Context ID: cli_session_20250623_120000

# Step 2: Implement suggestions
claude_cli(
  prompt="Add type hints as suggested",
  context_id="cli_session_20250623_120000"
)

# Step 3: Add tests
claude_cli(
  prompt="Create unit tests for the updated code",
  context_id="cli_session_20250623_120000"
)
```

### Example 2: Using Latest Session
```
# Initial task
claude_cli(prompt="Create a README for this project")

# Continue with latest session
claude_cli(
  prompt="Add installation instructions",
  context_id="latest"
)
```

## Troubleshooting

### Claude CLI Not Found
- Install with: `npm install -g @anthropic-ai/claude-cli`
- Verify installation: Use `claude_cli_version()` tool

### Session Not Found
- Check available sessions: `list_claude_cli_sessions()`
- Verify context_id spelling
- Use "latest" for most recent session

### No Output Received
- Check Claude CLI installation
- Verify working directory permissions
- Review logs for detailed error messages