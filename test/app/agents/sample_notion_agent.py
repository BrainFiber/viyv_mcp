from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
# import os, json, logging, openai

# from agents import Runner, enable_verbose_stdout_logging

# # ---- ログ設定 --------------------------
# enable_verbose_stdout_logging()        # SDK の内部ログ
# openai.log = "debug"                   # HTTP リクエスト／レスポンス全文
# logging.basicConfig(level=logging.DEBUG)


@agent(
    name="notion_agent",
    description="Notion ページを取得するツール",
    use_tools=["API-post-search","API-retrieve-a-page"],
)
async def notion_agent(query: str) -> str:

    # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
    oa_tools = build_function_tools(use_tools=["API-post-search", "API-retrieve-a-page"])
    print(oa_tools)

    # --- ③ エージェント定義 ----------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="NotionAgent",
        instructions=(
            "あなたは、Notion ページを取得するツールです。Tools を使って、Notion ページを取得してください。",
            "再帰的に Notion ページを取得し、詳細の情報を取得してください。",
            ),
        model="o4-mini-2025-04-16",
        tools=oa_tools,
        # 一旦１回の検索結果を返します。本来であれば、結果の型を定義して、ほしい結果を返すようにすれば、いい
        tool_use_behavior="stop_on_first_tool"
    )

    # --- ④ 実行 ----------------------------------------------------------
    try:
        result = await Runner.run(agent_, query)
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"