# app/agents/calc_agent.py
"""
Calc Agent (簡易電卓):
 - FastMCP の add ツールを OpenAI Agents SDK で利用。
"""

import re

from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
import os, json, logging, openai

from agents import Runner, enable_verbose_stdout_logging

# ---- ログ設定 --------------------------
# enable_verbose_stdout_logging()        # SDK の内部ログ
# openai.log = "debug"                   # HTTP リクエスト／レスポンス全文
# logging.basicConfig(level=logging.DEBUG)


@agent(
    name="calc_agent",
    description="add ツールを使った簡易電卓 (OpenAI Agents SDK 版)",
    use_tools=["add", "subtract"],
)
async def calc_agent(expression: str) -> str:
    # --- ① 式から 2 整数抽出 ------------------------------------------------
    nums = [int(x) for x in re.findall(r"-?\d+", expression)]
    if len(nums) != 2:
        raise ValueError("整数を 2 つ含む式を入力してください (例: '3 + 8')")
    a, b = nums

    # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
    oa_tools = build_function_tools(use_tools=["add", "subtract"])
    print(oa_tools)

    # --- ③ エージェント定義 ----------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="Calculator",
        instructions=(
            "あなたは電卓として振る舞う AI アシスタントです。"
            "与えられた式を計算し、結果のみを日本語で簡潔に答えてください。必ず適切なtoolを使用してください。"
        ),
        model="o3-mini",
        tools=oa_tools,
    )

    # --- ④ 実行 ----------------------------------------------------------
    try:
        result = await Runner.run(agent_, f"{a} + {b}")
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"