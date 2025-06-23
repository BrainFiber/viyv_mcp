from typing import Annotated

from pydantic import Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
import os, json, logging, openai

from agents import Runner, enable_verbose_stdout_logging

# ---- ログ設定 --------------------------
# enable_verbose_stdout_logging()        # SDK の内部ログ
# openai.log = "debug"                   # HTTP リクエスト／レスポンス全文
# logging.basicConfig(level=logging.DEBUG)


@agent(
    name="think_agent",
    description="次のアクションを考えるエージェントです。指示に従い、次のアクションを考えます。",
)
async def think_agent(
    instruction: Annotated[
        str,
        Field(title="現在の作業状況と結果を入力する")
    ],
    parent_system_prompt: Annotated[
        str,
        Field(title="親Agentの system_prompt（設定）を入力する")
    ],
) -> str:

    # --- ③ エージェント定義 ----------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="think_agent",
        instructions=(
            "あなたは、指示に従い、次のアクションを考える AI アシスタントです。",
            "現在の作業状況と結果から次のアクションを考えます。",
        ),
        model="o4-mini-2025-04-16",
    )

    # --- ④ 実行 ----------------------------------------------------------
    try:
        result = await Runner.run(agent_, f"{instruction} {parent_system_prompt}")
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"