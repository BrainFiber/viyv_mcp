"""
Claude CLI MCP tool implementation with advanced session management
Based on the test implementation with improvements
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Annotated
from datetime import datetime
from viyv_mcp import tool
from viyv_mcp.run_context import RunContext
from agents import RunContextWrapper
from pydantic import Field
from fastmcp import FastMCP
import logging
import shutil

logger = logging.getLogger(__name__)

# Session information storage file
SESSION_FILE = Path(__file__).parent.parent / "claude_cli_sessions.json"

# Lock for file operations
_file_lock = asyncio.Lock()

async def load_sessions() -> Dict[str, Any]:
    """Load saved session information (async with lock)"""
    async with _file_lock:
        if SESSION_FILE.exists():
            with open(SESSION_FILE, 'r') as f:
                return json.load(f)
        return {}

async def save_sessions(sessions: Dict[str, Any]):
    """Save session information (async with lock)"""
    async with _file_lock:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)

async def save_session_info(context_id: str, session_id: str = None, messages: List[str] = None, metadata: Dict[str, Any] = None):
    """Save session information"""
    sessions = await load_sessions()
    session_data = sessions.get(context_id, {})
    
    if session_id:
        session_data["session_id"] = session_id
    
    if messages is not None:
        session_data["messages"] = session_data.get("messages", []) + messages
    
    session_data["last_updated"] = datetime.now().isoformat()
    session_data["metadata"] = metadata or session_data.get("metadata", {})
    session_data["total_messages"] = len(session_data.get("messages", []))
    
    sessions[context_id] = session_data
    await save_sessions(sessions)

async def run_claude_cli(prompt: str, context_id: str, cwd: str = None, max_turns: int = 3) -> str:
    """Execute Claude CLI directly with session support"""
    logger.info(f"run_claude_cli called with prompt: {prompt[:50]}..., context_id: {context_id}")
    
    # Check if Claude CLI is installed
    claude_path = shutil.which('claude')
    if not claude_path:
        return "Error: Claude CLI is not installed. Please install it first with: npm install -g @anthropic-ai/claude-cli"
    logger.info(f"Claude CLI found at: {claude_path}")
    
    # Setup working directory
    if cwd:
        working_dir = Path(cwd)
    else:
        working_dir = Path(__file__).parent.parent / "claude_workspace"
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # Check existing session information
    sessions = await load_sessions()
    logger.info(f"Available sessions: {list(sessions.keys())}")
    stored_session_id = None
    
    if context_id in sessions:
        session_data = sessions[context_id]
        stored_session_id = session_data.get("session_id")
        if stored_session_id:
            logger.info(f"Found existing session {context_id} with session_id: {stored_session_id}")
        else:
            logger.warning(f"Session {context_id} exists but has no session_id")
    else:
        logger.info(f"Session {context_id} not found in sessions")
    
    # Get previous work context from session history
    session_context = ""
    if context_id in sessions and stored_session_id:
        # Include summary of previous work in prompt
        messages = session_data.get("messages", [])
        if messages:
            session_context = f" (Previous work: {session_data.get('metadata', {}).get('last_action', 'file operations performed')})"
            logger.info(f"Adding session context: {session_context}")
    
    # Add context to prompt
    full_prompt = f"{prompt}{session_context}" if session_context else prompt
    
    # Build CLI command
    cmd = ["claude", "-p", full_prompt, "--output-format", "stream-json", "--verbose"]
    
    # Add resume ID if available
    if stored_session_id:
        cmd.extend(["--resume", stored_session_id])
        # Increase max_turns when resuming
        if max_turns == 1:
            max_turns = 5
        logger.info(f"Using --resume with session_id: {stored_session_id}")
    
    # Other options
    cmd.extend([
        "--max-turns", str(max_turns),
        "--permission-mode", "acceptEdits"
    ])
    
    # Set environment variables
    env = os.environ.copy()
    
    try:
        # Execute subprocess
        logger.info(f"Executing command: {' '.join(cmd)}")
        logger.info(f"Working directory: {working_dir}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
            env=env
        )
        logger.info("Process started successfully")
        
        response_text = []
        current_session_id = None
        all_messages = []
        
        # Read stdout stream
        line_count = 0
        async for line in process.stdout:
            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue
            line_count += 1
            
            try:
                data = json.loads(line_str)
                
                # Get session_id from init message
                if data.get("type") == "system" and data.get("subtype") == "init":
                    session_id = data.get("session_id")
                    if session_id:
                        current_session_id = session_id
                        logger.info(f"Got session_id from CLI: {session_id}")
                        response_text.append(f"🚀 Session initialized")
                        response_text.append(f"  Session ID: {session_id}")
                        response_text.append(f"  Working directory: {data.get('cwd', 'unknown')}")
                
                # Assistant messages
                elif data.get("type") == "assistant" and "message" in data:
                    message = data["message"]
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    response_text.append(item.get("text", ""))
                                elif isinstance(item, dict) and item.get("type") == "tool_use":
                                    tool_name = item.get("name", "unknown")
                                    response_text.append(f"\n🔧 Using tool: {tool_name}")
                        elif isinstance(content, str):
                            response_text.append(content)
                
                # Error messages
                elif data.get("subtype") == "error_max_turns":
                    response_text.append(f"\n⚠️ Maximum turns ({data.get('num_turns', 'N/A')}) reached")
                
                # Result messages
                elif data.get("type") == "result":
                    if data.get("is_error"):
                        response_text.append(f"\n❌ Error occurred during execution")
                    else:
                        response_text.append(f"\n✅ Execution completed")
                        response_text.append(f"  Total turns: {data.get('num_turns', 0)}")
                        response_text.append(f"  Duration: {data.get('duration_ms', 0)}ms")
                
                all_messages.append(line_str)
                
            except json.JSONDecodeError:
                # Ignore non-JSON output
                pass
        
        # Wait for process to complete
        await process.wait()
        logger.info(f"Process completed. Processed {line_count} lines")
        
        # Check stderr
        stderr = await process.stderr.read()
        if stderr:
            logger.warning(f"Stderr output: {stderr.decode('utf-8')}")
        
        # Update session information
        session_id_to_save = current_session_id or stored_session_id
        if session_id_to_save:
            # Save work summary in metadata
            metadata = {
                "last_action": prompt[:100],
                "prompt": prompt,
                "result_summary": response_text[:200] if response_text else "No output"
            }
            await save_session_info(context_id, session_id=session_id_to_save, messages=all_messages, metadata=metadata)
        
        result = "\n".join(response_text) if response_text else "No response received"
        logger.info(f"Returning result (length: {len(result)} chars)")
        return result
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to execute Claude CLI: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"Failed to execute Claude CLI: {str(e)}"

def register(mcp: FastMCP):
    """Register tools with MCP"""
    logger.info("Registering Claude CLI tools...")
    
    @tool(description="Execute Claude CLI with session support (--resume)", tags={"claude", "cli", "code"})
    async def claude_cli(
        wrapper: RunContextWrapper[RunContext],
        prompt: Annotated[
            str,
            Field(
                title="Prompt",
                description="Prompt to send to Claude CLI",
            ),
        ],
        context_id: Annotated[
            Optional[str],
            Field(
                title="Context ID",
                description="Session ID for continuing conversation (omit for new session, 'latest' for most recent session)",
                default=None,
            ),
        ] = None,
        cwd: Annotated[
            Optional[str],
            Field(
                title="Working Directory",
                description="Directory path where Claude CLI operates",
                default=None,
            ),
        ] = None,
        max_turns: Annotated[
            int,
            Field(
                title="Max Turns",
                description="Maximum number of turns for Claude CLI interaction (recommended: 3+)",
                default=3,
                ge=1,
                le=10,
            ),
        ] = 3,
    ) -> str:
        """Execute code using Claude CLI directly with conversation history persistence via --resume"""
        logger.info(f"claude_cli called with context_id: {context_id}")
        
        # Process context_id
        if context_id == "latest":
            # Use the most recent session
            sessions = await load_sessions()
            
            if sessions:
                # Sort by last update time and get the most recent
                sorted_sessions = sorted(
                    sessions.items(),
                    key=lambda x: x[1].get("last_updated", ""),
                    reverse=True
                )
                context_id = sorted_sessions[0][0]
                logger.info(f"Using latest session: {context_id}")
            else:
                context_id = f"cli_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                logger.info(f"No existing sessions, generated new context_id: {context_id}")
        elif not context_id:
            # Generate new ID
            context_id = f"cli_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Generated new context_id: {context_id}")
        else:
            logger.info(f"Using provided context_id: {context_id}")
        
        result = await run_claude_cli(prompt, context_id, cwd, max_turns)
        
        return f"Context ID: {context_id}\n\n{result}"
    
    @tool(description="List Claude CLI sessions", tags={"claude", "cli", "session"})
    async def list_claude_cli_sessions(
        wrapper: RunContextWrapper[RunContext],
        limit: Annotated[
            int,
            Field(
                title="Display Limit",
                description="Number of sessions to display (from most recent)",
                default=10,
                ge=1,
                le=50,
            ),
        ] = 10,
    ) -> str:
        """Display list of saved Claude CLI sessions"""
        sessions = await load_sessions()
        
        if not sessions:
            return "No sessions found."
        
        # Sort by last update time
        sorted_sessions = sorted(
            sessions.items(),
            key=lambda x: x[1].get("last_updated", ""),
            reverse=True
        )[:limit]
        
        result = ["=== Claude CLI Sessions ===\n"]
        for context_id, session_data in sorted_sessions:
            last_updated = session_data.get("last_updated", "Unknown")
            last_action = session_data.get("metadata", {}).get("last_action", "No action recorded")
            message_count = session_data.get("total_messages", len(session_data.get("messages", [])))
            
            result.append(f"Context ID: {context_id}")
            result.append(f"  Last Updated: {last_updated}")
            result.append(f"  Last Action: {last_action[:50]}...")
            result.append(f"  Messages: {message_count}")
            result.append("")
        
        return "\n".join(result)
    
    @tool(description="Delete a Claude CLI session", tags={"claude", "cli", "session"})
    async def delete_claude_cli_session(
        wrapper: RunContextWrapper[RunContext],
        context_id: Annotated[
            str,
            Field(
                title="Context ID",
                description="Session ID to delete",
            ),
        ],
    ) -> str:
        """Delete a specific Claude CLI session"""
        sessions = await load_sessions()
        
        if context_id not in sessions:
            return f"Session '{context_id}' not found."
        
        del sessions[context_id]
        await save_sessions(sessions)
        
        return f"Session '{context_id}' deleted successfully."
    
    @tool(description="Get Claude CLI version and availability", tags={"claude", "cli", "info"})
    async def claude_cli_version(
        wrapper: RunContextWrapper[RunContext],
    ) -> str:
        """Check if Claude CLI is available and get version information"""
        claude_path = shutil.which('claude')
        
        if not claude_path:
            return "Claude CLI is not installed. Install with: npm install -g @anthropic-ai/claude-cli"
        
        try:
            # Get version
            process = await asyncio.create_subprocess_exec(
                "claude", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            version_info = stdout.decode('utf-8').strip() if stdout else "Unknown version"
            
            return f"Claude CLI available at: {claude_path}\nVersion: {version_info}"
            
        except Exception as e:
            return f"Error checking Claude CLI version: {str(e)}"