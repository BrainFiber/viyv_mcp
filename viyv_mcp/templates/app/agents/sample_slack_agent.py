from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
# import logging, openai

# from agents import Runner, enable_verbose_stdout_logging

# ---- ログ設定 --------------------------
# enable_verbose_stdout_logging()        # SDK の内部ログ
# openai.log = "debug"                   # HTTP リクエスト／レスポンス全文
# logging.basicConfig(level=logging.DEBUG)


@agent(
    name="slack_agent",
    description="slack チャンネル一覧を取得するツール",
    use_tools=["slack_list_channels"],
)
async def slack_agent(query: str) -> str:

    # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
    oa_tools = build_function_tools(use_tools=["slack_list_channels"])

    # --- ③ エージェント定義 ----------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="SlackAgent",
        instructions=(
            "あなたは、slack チャンネル一覧を取得するツールです。Tools を使って、slack チャンネル一覧を取得してください。"
        ),
        model="o4-mini-2025-04-16",
        tools=oa_tools,
    )

    # --- ④ 実行 ----------------------------------------------------------
    try:
        result = await Runner.run(agent_, query)
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"