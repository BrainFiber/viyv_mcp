"""
Claude CLI を直接使用したツール実装（--resume サポート版）
SDKのバージョンが古い場合の代替実装
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Annotated
from datetime import datetime
from viyv_mcp import tool
from pydantic import Field
import logging

logger = logging.getLogger(__name__)

# セッション情報を保存するファイル
SESSION_FILE = Path(__file__).parent.parent / "claude_cli_sessions.json"

# ファイル操作用のロック
_file_lock = asyncio.Lock()

async def load_sessions() -> Dict[str, Any]:
    """保存されたセッション情報を読み込む（非同期・ロック付き）"""
    async with _file_lock:
        if SESSION_FILE.exists():
            with open(SESSION_FILE, 'r') as f:
                return json.load(f)
        return {}

async def save_sessions(sessions: Dict[str, Any]):
    """セッション情報を保存する（非同期・ロック付き）"""
    async with _file_lock:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)

async def save_session_info(context_id: str, session_id: str = None, messages: List[str] = None, metadata: Dict[str, Any] = None):
    """セッション情報を保存"""
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

async def run_claude_cli(prompt: str, context_id: str, cwd: str = None, max_turns: int = 1) -> str:
    """Claude CLIを直接実行してコードを実行"""
    logger.info(f"run_claude_cli called with prompt: {prompt[:50]}..., context_id: {context_id}")
    
    # Claude CLIがインストールされているか確認
    import shutil
    claude_path = shutil.which('claude')
    if not claude_path:
        return "Error: Claude CLI is not installed. Please install it first: npm install -g @anthropic-ai/claude-cli"
    logger.info(f"Claude CLI found at: {claude_path}")
    
    # セッションファイルのパスを確認
    logger.info(f"Session file path: {SESSION_FILE}")
    
    # 作業ディレクトリの設定
    if cwd:
        working_dir = Path(cwd)
    else:
        working_dir = Path(__file__).parent.parent / "claude_workspace"
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # 既存のセッション情報を確認
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
    
    # セッション履歴から前回の作業内容を取得
    session_context = ""
    if context_id in sessions and stored_session_id:
        # 前回の作業内容を要約してプロンプトに含める
        messages = session_data.get("messages", [])
        if messages:
            session_context = f"（前回の作業: {session_data.get('metadata', {}).get('last_action', 'ファイル操作を実施')}）"
            logger.info(f"Adding session context: {session_context}")
    
    # プロンプトに文脈を追加
    full_prompt = f"{prompt}{session_context}" if session_context else prompt
    
    # CLIコマンドを構築
    cmd = ["claude", "-p", full_prompt, "--output-format", "stream-json", "--verbose"]
    
    # resume IDがある場合は追加
    if stored_session_id:
        cmd.extend(["--resume", stored_session_id])
        # 再開時はmax_turnsを増やす
        if max_turns == 1:
            max_turns = 5
        logger.info(f"Using --resume with session_id: {stored_session_id}")
    
    # その他のオプション
    cmd.extend([
        "--max-turns", str(max_turns),
        "--permission-mode", "acceptEdits"
    ])
    
    # 環境変数の設定
    env = os.environ.copy()
    
    try:
        # サブプロセスを実行
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
        
        # 標準出力をストリームで読み取り
        line_count = 0
        async for line in process.stdout:
            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue
            line_count += 1
            
            try:
                data = json.loads(line_str)
                
                # initメッセージからsession_idを取得
                if data.get("type") == "system" and data.get("subtype") == "init":
                    session_id = data.get("session_id")
                    if session_id:
                        current_session_id = session_id
                        logger.info(f"Got session_id from CLI: {session_id}")
                        response_text.append(f"🚀 Session initialized")
                        response_text.append(f"  Session ID: {session_id}")
                        response_text.append(f"  Working directory: {data.get('cwd', 'unknown')}")
                
                # アシスタントメッセージ
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
                
                # エラーメッセージ
                elif data.get("subtype") == "error_max_turns":
                    response_text.append(f"\n⚠️ Maximum turns ({data.get('num_turns', 'N/A')}) reached")
                
                # 結果メッセージ
                elif data.get("type") == "result":
                    if data.get("is_error"):
                        response_text.append(f"\n❌ Error occurred during execution")
                    else:
                        response_text.append(f"\n✅ Execution completed")
                        response_text.append(f"  Total turns: {data.get('num_turns', 0)}")
                        response_text.append(f"  Duration: {data.get('duration_ms', 0)}ms")
                
                all_messages.append(line_str)
                
            except json.JSONDecodeError:
                # JSON以外の出力は無視
                pass
        
        # プロセスの終了を待つ
        await process.wait()
        logger.info(f"Process completed. Processed {line_count} lines")
        
        # エラー出力を確認
        stderr = await process.stderr.read()
        if stderr:
            logger.warning(f"Stderr output: {stderr.decode('utf-8')}")
        
        # セッション情報を更新
        session_id_to_save = current_session_id or stored_session_id
        if session_id_to_save:
            # 作業内容の要約をメタデータに保存
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

def register(mcp):
    """MCPにツールを登録"""
    logger.info("Registering claude_cli tool...")

    @tool(description="Claude CLIを使用したコード実行（--resumeサポート版）", tags={"claude", "cli", "code"})
    async def claude_cli(
        prompt: Annotated[
            str,
            Field(
                title="プロンプト",
                description="Claude CLIに送るプロンプト",
            ),
        ],
        context_id: Annotated[
            Optional[str],
            Field(
                title="コンテキストID",
                description="会話を継続するためのセッションID（省略時は新規セッション、'latest'で最新セッション使用）",
                default=None,
            ),
        ] = None,
        cwd: Annotated[
            Optional[str],
            Field(
                title="作業ディレクトリ",
                description="Claude CLIが動作するディレクトリパス",
                default=None,
            ),
        ] = None,
        max_turns: Annotated[
            int,
            Field(
                title="最大ターン数",
                description="Claude CLIとの対話の最大ターン数（推奨: 3以上）",
                default=3,
                ge=1,
                le=10,
            ),
        ] = 3,
    ) -> str:
        """Claude CLIを直接使用してコードを実行し、--resumeで会話履歴を保持する"""
        logger.info(f"claude_cli called with context_id: {context_id}")
        
        # context_idの処理
        if context_id == "latest":
            # 最新のセッションを使用
            sessions = await load_sessions()

            if sessions:
                # 最終更新日時でソートして最新を取得
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
            # 新規IDを生成
            context_id = f"cli_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Generated new context_id: {context_id}")
        else:
            logger.info(f"Using provided context_id: {context_id}")
        
        result = await run_claude_cli(prompt, context_id, cwd, max_turns)
        
        return f"Context ID: {context_id}\n\n{result}"
    
    @tool(description="Claude CLIのセッション一覧を表示", tags={"claude", "cli", "session"})
    async def list_claude_cli_sessions(
        limit: Annotated[
            int,
            Field(
                title="表示数",
                description="表示するセッション数（最新から）",
                default=10,
                ge=1,
                le=50,
            ),
        ] = 10,
    ) -> str:
        """保存されているClaude CLIセッション一覧を表示"""
        sessions = await load_sessions()
        
        if not sessions:
            return "No sessions found."
        
        # 最終更新日時でソート
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