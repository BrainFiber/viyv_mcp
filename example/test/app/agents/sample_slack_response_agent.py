from typing import Annotated

from pydantic import Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
# import os, json, logging, openai

# from agents import Runner, enable_verbose_stdout_logging

# # ---- ログ設定 --------------------------
# enable_verbose_stdout_logging()  # SDK の内部ログ
# openai.log = "debug"  # HTTP リクエスト／レスポンス全文
# logging.basicConfig(level=logging.DEBUG)


@agent(
    name="slack_response_agent",
    description="slack を操作するエージェントです。指示に従いslack を操作します。必ず指示を与えてください。",
    use_tags=["slack"],
)
async def slack_response_agent(
    thread_ts: Annotated[
        str,
        Field(
            title="スレッドのタイムスタンプ",
            description="スレッドに返信する場合は、スレッドのタイムスタンプを指定してください。",
        ),
    ],
    channel_id: Annotated[
        str,
        Field(
            title="チャンネルID",
            description="スレッドに返信する場合は、スレッドのチャンネルIDを指定してください。",
        ),
    ],
    user_id: Annotated[
        str,
        Field(
            title="ユーザーID",
            description="スレッドに返信する場合は、スレッドのユーザーIDを指定してください。",
        ),
    ],
    reply_text: Annotated[
        str,
        Field(
            title="返信内容",
            description="スレッドに返信する内容を指定してください。",
        ),
    ],
) -> str:

    # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
    oa_tools = build_function_tools(use_tools=["slack_reply_to_thread"])

    # --- ③ エージェント定義 ----------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="SlackResponseAgent",
        instructions=(
            "あなたは、指示に従い、slack ワークスペースを操作する AI アシスタントです。",
            "",
        ),
        model="o4-mini-2025-04-16",
        tools=oa_tools,
    )

    # --- ④ 実行 ----------------------------------------------------------
    try:
        result = await Runner.run(agent_, f"スレッドのタイムスタンプ：{thread_ts} チャンネルID：{channel_id} ユーザーID：{user_id} 返信内容：{reply_text}")
        # 
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"
