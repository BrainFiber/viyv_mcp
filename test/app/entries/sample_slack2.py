# sample_slack.py
# ===========================================================================
# Slack Bolt + FastAPI + viyv_mcp integration
#
# ❶ /slack2/events  → Bolt adapter (Slash-Command & Events API)
# ❷ /slack2/health → ヘルスチェック
#
# ・画像付きメンション   → GPT-4o Vision で解析
# ・画像が無いメンション → 「画像がありません」と返す
# ---------------------------------------------------------------------------

from __future__ import annotations
from typing import Annotated, List, Optional, Tuple

import base64
import imghdr
import logging
import os
import re
import uuid
import pathlib
from io import BytesIO
from urllib.parse import unquote, urlparse

import aiohttp
from PIL import Image
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_sdk.web.async_client import AsyncWebClient

from app.utils.slack_utils import convert_markdown_to_slack
from viyv_mcp.decorators import entry
from viyv_mcp.openai_bridge import build_function_tools
from openai.types.shared import Reasoning

from agents import Agent as OAAgent, ModelSettings, Runner

# ─────────────────── Slack 環境変数 ─────────────────────────────────────
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")  # 例: "https://example.com"

# ─────────────────────── 定数 ────────────────────────────────────────────
ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB

# 画像保存先ディレクトリ（環境変数 UPLOAD_DIR で上書き可）
UPLOAD_DIR = pathlib.Path(
    os.getenv("UPLOAD_DIR", os.path.join(os.getcwd(), "static", "upload"))
)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────── グローバル ──────────────────────────────────────
BOT_USER_ID: str = ""  # 起動時に auth.test で取得して保持する


# ──────────────────── ヘルパ関数 ─────────────────────────────────────────
async def slack_file_to_base64(url: str, token: str) -> Tuple[str, str, bytes]:
    """
    Slack の private URL → (mime_type, base64_string, raw_bytes).
    """
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(headers=headers) as sess:
        async with sess.get(url, allow_redirects=True) as resp:
            resp.raise_for_status()
            data = await resp.read()

    if not data:
        raise ValueError("画像データが空です")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("画像サイズが 10 MiB を超えています")

    fmt = imghdr.what(None, data)
    mime = {
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(fmt)

    if mime is None:
        try:
            with Image.open(BytesIO(data)) as img:
                mime = {
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }.get(img.format.lower())
        except Exception:
            mime = None

    if mime not in ALLOWED_MIME:
        raise ValueError("OpenAI が対応していない画像形式、または画像が壊れています")

    Image.open(BytesIO(data)).verify()
    return mime, base64.b64encode(data).decode("ascii"), data


async def build_thread_messages(
    event: dict, client: AsyncWebClient
) -> Tuple[List[dict], Optional[str]]:
    """
    スレッド履歴を取得し、Agents SDK 向け messages 配列を構築し、
    さらに metadata に埋め込まれた response_id を取得する。
    """
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("event_ts")
    if not (channel and thread_ts):
        return [], None

    try:
        resp = await client.conversations_replies(
            channel=channel, ts=thread_ts, inclusive=True, limit=1000, include_all_metadata=True
        )
        replies = sorted(resp["messages"], key=lambda m: float(m.get("ts", 0)))
    except Exception as exc:
        logging.warning(f"Failed to fetch thread replies: {exc}")
        return [], None

    history: List[dict] = []
    last_response_id: Optional[str] = None

    for m in replies:
        text = m.get("text", "")
        if BOT_USER_ID:
            mention_re = re.compile(rf"<@{re.escape(BOT_USER_ID)}(\|[^>]+)?>")
            text = mention_re.sub("(AI アシスタントへ問い合わせ)", text).strip()

        role = (
            "assistant" if m.get("user") == BOT_USER_ID or m.get("bot_id") else "user"
        )
        if text:
            history.append({"role": role, "content": text})

    # 最後の assistant メッセージから response_id を抽出
    for m in reversed(replies):
        metadata = m.get("metadata", {})
        if (
            metadata.get("event_type") == "agent_response"
            and "event_payload" in metadata
            and "response_id" in metadata["event_payload"]
        ):
            last_response_id = metadata["event_payload"]["response_id"]
            break

    return history, last_response_id


# ────────────────────── FastAPI エントリ ──────────────────────────────────
@entry("/slack2", use_tools=["slack_agent", "notion_agent", "image_agent"])
def slack_entry() -> FastAPI:
    """Slack Events を受け付ける FastAPI サブアプリ"""
    bolt_app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

    async def fetch_bot_user_id():
        global BOT_USER_ID
        if BOT_USER_ID:
            return
        res = await bolt_app.client.auth_test()
        BOT_USER_ID = res["user_id"]
        logging.info(f"Bot User ID: {BOT_USER_ID}")

    api = FastAPI(title="Slack Webhook (Bolt)")

    @api.on_event("startup")
    async def on_startup():
        await fetch_bot_user_id()

    # ───────── メンションイベント ────────────────────────────
    @bolt_app.event("app_mention")
    async def handle_mention(event: dict, say):
        global BOT_USER_ID
        if not BOT_USER_ID:
            await fetch_bot_user_id()

        text: str = event.get("text", "") or ""
        files = event.get("files", []) or []

        if BOT_USER_ID:
            mention_re = re.compile(rf"<@{re.escape(BOT_USER_ID)}(\|[^>]+)?>")
            text = mention_re.sub("(AI アシスタントへ問い合わせ)", text).strip()

        # 添付画像処理
        image_items: List[dict] = []
        saved_urls: List[str] = []  # ★★★ URL を保持
        for f in files:
            if not f.get("mimetype", "").startswith("image/"):
                continue
            url = f.get("url_private_download") or f.get("url_private")
            if not url:
                continue
            try:
                mime, b64, raw_bytes = await slack_file_to_base64(url, SLACK_BOT_TOKEN)

                # ---------- 保存 & URL 生成 --------------------------- ★★★
                ext = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/gif": "gif",
                    "image/webp": "webp",
                }.get(mime, "img")
                filename = f"{uuid.uuid4()}.{ext}"
                file_path = UPLOAD_DIR / filename
                with file_path.open("wb") as fp:
                    fp.write(raw_bytes)

                # /static/upload/... に変換
                rel_path = file_path.relative_to(UPLOAD_DIR.parent)  # upload/xxxx.jpg
                static_url = f"{BASE_URL}/static/{rel_path.as_posix()}"
                saved_urls.append(static_url)
                # ------------------------------------------------------

                image_items.append(
                    {
                        "type": "input_image",
                        "detail": "auto",
                        "image_url": f"data:{mime};base64,{b64}",
                    }
                )
            except ValueError as e:
                await say(f"画像をスキップしました: {e}")

        # Tools を変換
        oa_tools = build_function_tools()

        class Response(BaseModel):
            text: Annotated[str, Field(..., title="返信メッセージ本文")]
            image_urls: Annotated[
                Optional[List[str]],
                Field(None, title="画像 URLs"),
            ]

        vision_agent = OAAgent(
            name="VisionAssistant",
            model="o4-mini-2025-04-16",
            instructions=(
                "あなたはマルチモーダル・ユーザサポートAIアシスタントです。"
                "ユーザーからの質問を理解し、日本語で簡潔に回答してください。"
                "Slack 上で読みやすいように整形してください。"
                "可能な限り、並列でツールを呼び出してください。"
            ),
            output_type=Response,
            tools=oa_tools,
            model_settings=ModelSettings(
                parallel_tool_calls=True,
                reasoning=Reasoning(effort="high"),
            ),
        )

        client: AsyncWebClient = bolt_app.client
        history_messages, last_response_id = await build_thread_messages(event, client)

        # ★★★ URL を message に含める
        saved_urls_text = (
            "\n".join(f"添付画像 URL: {u}" for u in saved_urls) if saved_urls else ""
        )

        current_user_msg = {
            "role": "user",
            "content": f"""
            ユーザの問い合わせ: {text}
            ユーザid: {event.get("user", "")}
            チャンネルid: {event.get("channel", "")}
            スレッドのタイムスタンプ: {event.get("event_ts", "")}
            {saved_urls_text}
            """,
        }

        messages: List[dict] = []
        if image_items:
            messages.append({"role": "user", "content": image_items})

        messages.extend(history_messages)
        messages.append(current_user_msg)

        try:
            result = await Runner.run(vision_agent, messages, previous_response_id=last_response_id)

            await say(
                channel=event["channel"],
                thread_ts=event.get("thread_ts") or event["event_ts"],
                text=convert_markdown_to_slack(result.final_output.text),
                metadata={
                    "event_type": "agent_response",
                    "event_payload": {
                        "response_id": result.last_response_id,
                    },
                },
            )

            if result.final_output.image_urls:
                async with aiohttp.ClientSession() as sess:
                    for idx, url in enumerate(result.final_output.image_urls, start=1):
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

                        buf = BytesIO(img_bytes)
                        parsed = urlparse(url)
                        filename = (
                            os.path.basename(parsed.path) or f"reply_image_{idx}.png"
                        )
                        filename = unquote(filename)

                        await bolt_app.client.files_upload_v2(
                            channel=event["channel"],
                            file=buf,
                            filename=filename,
                            title=f"返信画像 {idx}",
                            thread_ts=event.get("thread_ts") or event["event_ts"],
                        )

        except Exception as exc:
            await say(f"Vision 呼び出しエラー: {exc}")

    # ──────────── Bolt → FastAPI ラッパ ─────────────────────────
    handler = AsyncSlackRequestHandler(bolt_app)

    @api.post("/events", include_in_schema=False)
    async def slack_events(req: Request):
        if (retry_num := req.headers.get("x-slack-retry-num")) and int(retry_num) > 0:
            return {"ok": True}
        return await handler.handle(req)

    @api.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    return api
