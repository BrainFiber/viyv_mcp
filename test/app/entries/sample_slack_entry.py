"""
/slack3 配下で VisionAgent を起動するエントリ。

* SlackAdapter にメンションハンドラを登録して返すだけ
* 長時間処理の場合 ────────────────────────────────────────
    1. 処理開始直後に “処理を開始しました …” をスレッドに投稿
    2. run_streamed() の stream_event に応じて ↑ のメッセージを chat.update で上書き
    3. 最終的に final_output.text で上書きして完了
* SlackAdapter が生成する **SlackRunContext** をそのまま利用
"""

from dataclasses import dataclass
import os
import pathlib
from typing import Annotated, Any, List, Optional
from urllib.parse import unquote, urlparse

import aiohttp
import openai
from pydantic import BaseModel, Field

from agents import Agent as OAAgent, ItemHelpers, ModelSettings, Runner
from openai.types.shared import Reasoning
from viyv_mcp.app.adapters.slack_adapter import (
    SlackAdapter,
)
from viyv_mcp.decorators import entry
from viyv_mcp.openai_bridge import build_function_tools
from app.utils.slack_utils import convert_markdown_to_slack
from viyv_mcp.run_context import RunContext

# ─── 環境変数 ──────────────────────────────────────────────────────────── #
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.getcwd(), "static", "upload"))

openai.log = "info"

@dataclass
class SlackRunContext(RunContext):
    channel: str
    thread_ts: str
    client:   Any
    progress_ts: Optional[str] = None

    async def post_start_message(self) -> None:
        res = await self.client.chat_postMessage(
            channel=self.channel,
            thread_ts=self.thread_ts,
            text=":hourglass_flowing_sand: 処理を開始しました…",
        )
        self.progress_ts = res["ts"]

    async def update_progress(self, text:str) -> None:
        if not self.progress_ts:
            await self.post_start_message()
        await self.client.chat_update(
            channel=self.channel,
            ts=self.progress_ts,
            text=text,
        )

    async def post_new_message(self, text:str) -> None:
        await self.client.chat_postMessage(
            channel=self.channel,
            thread_ts=self.thread_ts,
            text=text,
        )

# ─── エンドポイント定義 ───────────────────────────────────────────────── #
@entry(
    "/slack3",
    use_tools=["notion_agent", "image_agent", "file_analysis_agent", "image_analysis_agent"],
    use_tags=["cost"],
)
def slack_entry():
    """Slack endpoint factory"""

    adapter = SlackAdapter(
        bot_token=SLACK_BOT_TOKEN,
        signing_secret=SLACK_SIGNING_SECRET,
        base_url=BASE_URL,
        upload_dir=pathlib.Path(UPLOAD_DIR),
        context_cls=SlackRunContext,
    )

    # ── メンション後段ロジック ───────────────────────────────────────── #
    async def mention_handler(
        slack_event: dict,
        text: str,
        image_urls: List[str],
        file_urls: List[str],
        say,
        bolt_app,
        adp: SlackAdapter,
        run_ctx: SlackRunContext,   # ← adapter から渡される context
    ):
        # 0) 進捗用メッセージを投稿
        await run_ctx.post_start_message()

        # 1) 会話履歴取得
        history, last_id = await adp.build_thread_messages(slack_event, bolt_app.client)

        # 2) 会話 messages（ユーザ発話を末尾に追加）
        saved_images_text = "\n".join(f"添付画像 URL: {u}" for u in image_urls) if image_urls else ""
        saved_files_text = "\n".join(f"添付ファイル URL: {u}" for u in file_urls) if file_urls else ""
        current_user_msg = {
            "role": "user",
            "content": (
                f"ユーザの問い合わせ: {text}\n"
                f"ユーザid: {slack_event.get('user','')}\n"
                f"チャンネルid: {slack_event.get('channel','')}\n"
                f"スレッドのタイムスタンプ: {slack_event.get('event_ts','')}\n"
                f"{saved_images_text}\n{saved_files_text}"
            ),
        }
        messages = history + [current_user_msg]

        # 3) Agent & Tools
        gdft = adp.get_download_file_tool()
        tools = [gdft] + build_function_tools()
        prompt = await adp.fetch_channel_prompt(channel_id=slack_event["channel"])

        class Response(BaseModel):
            text: Annotated[str, Field(..., title="返信メッセージ本文")]
            image_urls: Optional[List[str]] = Field(None, title="画像 URLs")

        vision_agent = OAAgent[SlackRunContext](  # context 型を指定
            name="VisionAssistant",
            model="o4-mini-2025-04-16",
            instructions=(
                "あなたはマルチモーダル・ユーザサポートAIアシスタントです。"
                "ユーザーからの質問を理解し、日本語で簡潔に回答してください。"
                "Slack 上で読みやすいように整形してください。"
                "可能な限り、並列でツールを呼び出してください。\n"
                "次の指示に従ってください: " + prompt + "\n"
            ),
            output_type=Response,
            tools=tools,
            model_settings=ModelSettings(
                parallel_tool_calls=True,
                reasoning=Reasoning(effort="high"),
            ),
        )

        # 4) Agent 実行（streaming） – context=run_ctx
        result = Runner.run_streamed(
            vision_agent,
            messages,
            context=run_ctx,
            previous_response_id=last_id,
        )

        async for stream_event in result.stream_events():
            # run_item_stream_event → message_output_item のたびに更新
            if (
                stream_event.type == "run_item_stream_event"
                and stream_event.item.type == "message_output_item"
            ):
                partial_text = convert_markdown_to_slack(
                    ItemHelpers.text_message_output(stream_event.item)
                )
                await run_ctx.update_progress(partial_text)

        # 5) 最終結果でメッセージを更新
        final_text = convert_markdown_to_slack(result.final_output.text)
        await run_ctx.update_progress(final_text)

        # 6) 画像があれば別送
        if result.final_output.image_urls:
            async with aiohttp.ClientSession() as sess:
                for idx, url in enumerate(result.final_output.image_urls, 1):
                    try:
                        async with sess.get(url, allow_redirects=True) as resp:
                            resp.raise_for_status()
                            img_bytes = await resp.read()
                    except Exception:
                        await run_ctx.client.chat_postMessage(
                            channel=run_ctx.channel,
                            thread_ts=run_ctx.thread_ts,
                            text=f"画像 {idx} のダウンロードに失敗したため、添付をスキップしました。",
                        )
                        continue

                    from io import BytesIO

                    buf = BytesIO(img_bytes)
                    filename = os.path.basename(urlparse(url).path) or f"reply_{idx}.png"

                    await run_ctx.client.files_upload_v2(
                        channel=run_ctx.channel,
                        file=buf,
                        filename=unquote(filename),
                        title=f"返信画像 {idx}",
                        thread_ts=run_ctx.thread_ts,
                    )

    # ハンドラ登録
    adapter.register_mention_handler(mention_handler)

    # FastAPI サブアプリを返す
    return adapter.as_fastapi_app()