"""
/slack2 配下で VisionAgent を起動するエントリ。

* SlackAdapter にメンションハンドラを登録して返すだけ
"""

from __future__ import annotations
from typing import Annotated, List, Optional

import os
from urllib.parse import unquote, urlparse
from pydantic import BaseModel, Field

from viyv_mcp.decorators import entry
from viyv_mcp.app.adapters.slack_adapter import SlackAdapter
from app.utils.slack_utils import convert_markdown_to_slack
from agents import Agent as OAAgent, ModelSettings, Runner
from openai.types.shared import Reasoning
import pathlib
import aiohttp

from viyv_mcp.openai_bridge import build_function_tools

# --- 環境変数 ----------------------------------------------------------- #
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.getcwd(), "static", "upload"))


# ---------------------------------------------------------------------- #
@entry("/slack3", use_tools=["notion_agent", "image_agent", "file_analysis_agent", "image_analysis_agent"])
def slack_entry():
    """Slack endpoint factory"""

    adapter = SlackAdapter(
        bot_token=SLACK_BOT_TOKEN,
        signing_secret=SLACK_SIGNING_SECRET,
        base_url=BASE_URL,
        upload_dir=pathlib.Path(UPLOAD_DIR),
    )

    # ---- メンション後段ロジック ---------------------------------------- #
    async def mention_handler(
        event,
        text,
        image_urls,
        file_urls,          # ★ 追加
        say,
        bolt_app,
        adp: SlackAdapter,
    ):
        # 1) 会話履歴
        history, last_id = await adp.build_thread_messages(event, bolt_app.client)

        # 2) messages 構築
        saved_images_text = (
            "\n".join(f"添付画像 URL: {u}" for u in image_urls) if image_urls else ""
        )
        saved_files_text = (
            "\n".join(f"添付ファイル URL: {u}" for u in file_urls) if file_urls else ""
        )
        current_user_msg = {
            "role": "user",
            "content": (
                f"ユーザの問い合わせ: {text}\n"
                f"ユーザid: {event.get('user','')}\n"
                f"チャンネルid: {event.get('channel','')}\n"
                f"スレッドのタイムスタンプ: {event.get('event_ts','')}\n"
                f"{saved_images_text}\n{saved_files_text}"
            ),
        }

        messages = history + [current_user_msg]

        # Tools を変換
        oa_tools = build_function_tools()

        gdft = adp.get_download_file_tool()

        tools = [
            gdft,
        ] + oa_tools

        prompt = await adp.fetch_channel_prompt(channel_id=event["channel"])

        # --- Agent 出力型 ------------------------------------------------------- #
        class Response(BaseModel):
            text: Annotated[str, Field(..., title="返信メッセージ本文")]
            image_urls: Optional[List[str]] = Field(None, title="画像 URLs")


        # --- Agent ------------------------------------------------------------- #
        vision_agent = OAAgent(
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
            tools=tools,  # `build_function_tools()` は自動注入される
            model_settings=ModelSettings(
                parallel_tool_calls=True,
                reasoning=Reasoning(effort="high"),
            ),
        )


        # 3) Agent 実行
        result = await Runner.run(
            vision_agent, messages, previous_response_id=last_id
        )

        # 4) テキスト返信
        await say(
            channel=event["channel"],
            thread_ts=event.get("thread_ts") or event["event_ts"],
            text=convert_markdown_to_slack(result.final_output.text),
            metadata={
                "event_type": "agent_response",
                "event_payload": {"response_id": result.last_response_id},
            },
        )

        # 5) 画像返信（あれば）
        if result.final_output.image_urls:
            async with aiohttp.ClientSession() as sess:
                for idx, url in enumerate(result.final_output.image_urls, 1):
                    try:
                        async with sess.get(url, allow_redirects=True) as resp:
                            resp.raise_for_status()
                            img_bytes = await resp.read()
                    except Exception:
                        await say(
                            channel=event["channel"],
                            thread_ts=event.get("thread_ts") or event["event_ts"],
                            text=f"画像 {idx} のダウンロードに失敗したため、添付をスキップしました。",
                        )
                        continue

                    from io import BytesIO

                    buf = BytesIO(img_bytes)
                    filename = os.path.basename(urlparse(url).path) or f"reply_{idx}.png"

                    await bolt_app.client.files_upload_v2(
                        channel=event["channel"],
                        file=buf,
                        filename=unquote(filename),
                        title=f"返信画像 {idx}",
                        thread_ts=event.get("thread_ts") or event["event_ts"],
                    )

    # ハンドラ登録
    adapter.register_mention_handler(mention_handler)

    # FastAPI サブアプリを返す
    return adapter.as_fastapi_app()