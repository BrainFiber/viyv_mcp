# sample_slack.py
#
# Slack Bolt + FastAPI + viyv_mcp integration
# ------------------------------------------
# ❶ /slack/events  ──> Bolt adapter (Slash Command & Events API 共通エンドポイント)
# ❷ /slack/health  ──> アプリ稼働確認用
#
# * `@entry("/slack", use_tags=["slack"])`
#     → “slack” タグ付き FastMCP ツールを ContextVar に自動注入
# * ハンドラ内では `build_function_tools()` をそのまま呼び出せる
# * 署名検証は Bolt が自動で行う（signing secret 必要）
# ---------------------------------------------------------------------------

import os
from agents import ModelSettings
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from viyv_mcp.decorators import entry
from viyv_mcp.openai_bridge import build_function_tools


# Slack 環境変数（config.json 側で渡しても OK）
SLACK_BOT_TOKEN      = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")


@entry("/slack", use_tools=["slack_agent", "slack_response_agent", "notion_agent"])
def slack_entry() -> FastAPI:
    """
    Slack Slash Command / イベント受付用 FastAPI サブアプリ
    """
    # ----- 1. Bolt アプリ ---------------------------------------------------
    bolt_app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

    # -- 1-A. Slash Command (/gpt) ------------------------------------------
    @bolt_app.command("/gpt")
    async def handle_gpt(ack, body, respond):
        await ack()                                   # 3 秒以内に ACK

        prompt = body.get("text", "").strip() or "slack チャンネル一覧を取得してください"

        # FastMCP → OpenAI Agents SDK Tool 変換
        oa_tools = build_function_tools()

        try:
            from agents import Agent as OAAgent, Runner
        except ImportError:
            await respond("`openai-agents-python` が入っていません。`pip install openai-agents-python`")
            return

        agent_ = OAAgent(
            name="SlackAssistant",
            instructions=(
                "あなたは Slack ワークスペースを操作・レポートする AI アシスタントです。"
                "必ず tool を活用して回答してください。"
            ),
            model="o4-mini-2025-04-16",
            tools=oa_tools,
        )

        try:
            result = await Runner.run(agent_, prompt)
            await respond(str(result.final_output))
        except Exception as exc:
            await respond(f"Agent error: {exc}")

    # -- 1-B. App Mention イベント ------------------------------------------
    @bolt_app.event("app_mention")
    async def handle_mention(event, say):
        text = str(event)

        slack_history_tools = build_function_tools(use_tools=["slack_agent"])
        notion_tools = build_function_tools(use_tools=["notion_agent"])
        slack_response_tools = build_function_tools(use_tools=["slack_response_agent"], exclude_tools=["notion_agent"])
        from agents import Agent as OAAgent, Runner

        history_agent = OAAgent(
            name="HistoryAgent",
            instructions=(
                "あなたは、スレッドの過去のメッセージを確認し、質問に関連する内容を取得する AI アシスタントです。",
                "スレッドの過去のメッセージから、質問に関連する内容を取得してください。",
            ),
            model="o4-mini-2025-04-16",
            model_settings=ModelSettings(reasoning={"effort": "high"}),
            tools=slack_history_tools,
        )

        agent_ = OAAgent(
            name="SlackAssistant",
            instructions=(
                "あなたは ユーザをサポートする AI アシスタントです。",
                "ユーザの質問に答えるために必要な情報をToolを利用し収集してください",
                "情報収集が必要無ければ、何もせずにスルーしてください。",
            ),
            model="o4-mini-2025-04-16",
            tools=notion_tools,
            model_settings=ModelSettings(reasoning={"effort": "high"}),
        )

        response_agent = OAAgent(
            name="ResponseAgent",
            instructions=(
                "あなたは slacktoolを利用して、ユーザに回答する AI アシスタントです。",
                "必ず tool を活用して回答してください。必ずスレッドに返信してください。",
            ),
            model="o4-mini-2025-04-16",
            model_settings=ModelSettings(reasoning={"effort": "high"}),
            tools=slack_response_tools,
        )
        try:
            history_result = await Runner.run(
                history_agent,
                f"スレッドの過去のメッセージから、質問に関連する内容を取得してください。質問：{text}",
            )
            result = await Runner.run(agent_, f"ユーザの質問に答えるために必要な情報をToolを利用し収集してください。メッセージ：{text} 過去のやり取り：{history_result.final_output}")
            print(str(result))
            await Runner.run(
                response_agent,
                f"下記内容をユーザに回答してください。回答内容：{result.final_output} 元のメッセージ：{text}",
            )
        except Exception as exc:
            await say(f"Agent error: {exc}")

    # ----- 2. FastAPI ラッパ ------------------------------------------------
    api = FastAPI(title="Slack Webhook (Bolt)")

    handler = AsyncSlackRequestHandler(bolt_app)

    @api.post("/events", include_in_schema=False)
    async def slack_events(req: Request):
        return await handler.handle(req)

    @api.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    return api