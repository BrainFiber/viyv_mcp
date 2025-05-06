"""
Slack Bolt + FastAPI を『ひとことで呼べる』アダプタ。

* mention_handler(event, text, image_urls, say, bolt_app, adapter)
    を登録すると、@メンション時の後段ロジックだけを書けば済む。
"""

from __future__ import annotations
from typing import Annotated, Awaitable, Callable, List, Optional, Tuple

import asyncio
import base64
import imghdr
import logging
import os
import pathlib
import re
import uuid
from io import BytesIO
from urllib.parse import unquote, urlparse

from agents import function_tool
import aiohttp
from fastapi import FastAPI, Request
from PIL import Image
from pydantic import Field
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_sdk.web.async_client import AsyncWebClient
from viyv_mcp.decorators import tool  # ★ 追加

logger = logging.getLogger(__name__)


PROMPT_START = "###prompt_start###"
PROMPT_END = "###prompt_end###"


class SlackAdapter:
    """Slack エンドポイントを FastAPI サブアプリとして提供"""

    # ---------- 初期化 -------------------------------------------------- #

    def __init__(
        self,
        *,
        bot_token: str,
        signing_secret: str,
        base_url: str = "http://localhost:8000",
        upload_dir: pathlib.Path = pathlib.Path("./static/upload"),
        allowed_mime: set[str]
        | None = {"image/png", "image/jpeg", "image/gif", "image/webp"},
        max_image_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.base_url = base_url.rstrip("/")
        self.upload_dir = upload_dir
        self.allowed_mime = allowed_mime or set()
        self.max_image_bytes = max_image_bytes

        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.bolt = AsyncApp(token=bot_token, signing_secret=signing_secret)
        self._handler: (
            Callable[
                [dict, str, List[str], Callable, AsyncApp, "SlackAdapter"],
                Awaitable[None],
            ]
            | None
        ) = None

        self._bot_user_id: str = ""
        self._register_startup()
        self._register_events()

    # ---------- 外部 API ----------------------------------------------- #

    def register_mention_handler(
        self,
        handler: Callable[
            [dict, str, List[str], Callable, AsyncApp, "SlackAdapter"], Awaitable[None]
        ],
    ):
        """@メンションイベント後段のコールバックを登録"""
        self._handler = handler

    def as_fastapi_app(self) -> FastAPI:
        """FastAPI サブアプリを返す（/events, /health を提供）"""
        api = FastAPI(title="Slack Webhook (viyv_mcp)")

        bolt_handler = AsyncSlackRequestHandler(self.bolt)

        @api.post("/events", include_in_schema=False)
        async def slack_events(req: Request):
            # Slack 再送 (retry-num > 0) は即 200 OK
            if (n := req.headers.get("x-slack-retry-num")) and int(n) > 0:
                return {"ok": True}
            return await bolt_handler.handle(req)

        @api.get("/health", include_in_schema=False)
        async def health():
            return {"status": "ok"}

        return api

    # ---------- 内部ユーティリティ ------------------------------------- #

    def _register_startup(self):
        """Bolt 起動時に bot_user_id を取得"""
        bolt = self.bolt

        @bolt.event("app_home_opened")  # 最初に必ず呼ばれる軽量イベント
        async def _once_logger(**payload):
            if self._bot_user_id:
                return
            res = await bolt.client.auth_test()
            self._bot_user_id = res["user_id"]
            logger.info(f"Bot User ID = {self._bot_user_id}")

    def _register_events(self):
        """@メンションイベントの共通前処理 → ユーザハンドラ呼び出し"""

        @self.bolt.event("app_mention")
        async def _handle_mention(event: dict, say):
            if not self._handler:
                await say("メンションは受信しましたが、ハンドラが未登録です。")
                return

            # -- ① テキスト整形 ------------------------------------------------
            text: str = event.get("text", "") or ""
            if self._bot_user_id:
                mention_re = re.compile(rf"<@{re.escape(self._bot_user_id)}(\|[^>]+)?>")
                text = mention_re.sub("(AI アシスタントへ問い合わせ)", text).strip()

            # -- ② 添付画像をローカル保存＆公開 URL 化 --------------------------
            files = event.get("files", []) or []
            saved_urls: List[str] = []
            for f in files:
                if not f.get("mimetype", "").startswith("image/"):
                    continue
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                try:
                    mime, raw = await self._download_image(url)
                    rel = self._save_image(mime, raw)
                    saved_urls.append(f"{self.base_url}/static/{rel.as_posix()}")
                except ValueError as e:
                    await say(f"画像をスキップしました: {e}")

            # -- ③ 後段コールバック -------------------------------------------
            await self._handler(
                event, text, saved_urls, say, self.bolt, self  # type: ignore[arg-type]
            )

    # -- 画像処理 ------------------------------------------------------------ #

    async def _download_image(self, url: str) -> Tuple[str, bytes]:
        """Slack private URL → (mime, raw_bytes)"""
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(url, allow_redirects=True) as resp:
                resp.raise_for_status()
                data = await resp.read()

        if not data:
            raise ValueError("画像データが空です")
        if len(data) > self.max_image_bytes:
            raise ValueError("画像サイズが 10 MiB を超えています")

        fmt = imghdr.what(None, data)
        mime = {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(fmt)
        if mime not in self.allowed_mime:
            raise ValueError("非対応画像です")

        # Pillow で壊れチェック
        Image.open(BytesIO(data)).verify()
        return mime, data

    def _save_image(self, mime: str, raw: bytes) -> pathlib.Path:
        """raw 画像 → upload_dir に保存し、static 配下の相対パスを返す"""
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}[
            mime
        ]
        filename = f"{uuid.uuid4()}.{ext}"
        path = self.upload_dir / filename
        with path.open("wb") as fp:  # type: ignore
            fp.write(raw)

        # 「…/static/upload/xxxx.jpg」部分だけ抜く
        return path.relative_to(self.upload_dir.parent)

    # ---------- プロンプト取得 --------------------------------------------- #

    async def fetch_channel_prompt(self, channel_id: str) -> Optional[str]:
        """チャンネルトピック／パーパスからプロンプト部分を抽出して返す。

        フォーマット:
        ###prompt_start###\n<任意のテキスト>\n###prompt_end###
        """
        empty = ""

        client: AsyncWebClient = self.bolt.client
        try:
            info = await client.conversations_info(channel=channel_id)
        except Exception as exc:
            logger.warning(f"Failed to fetch channel info: {exc}")
            return empty

        channel_obj = info.get("channel", {})
        topic_val = channel_obj.get("topic", {}).get("value", "") or ""
        purpose_val = channel_obj.get("purpose", {}).get("value", "") or ""

        # topic に定義があれば優先、無ければ purpose
        target = topic_val if PROMPT_START in topic_val else purpose_val
        if not target:
            return empty

        m = re.search(rf"{re.escape(PROMPT_START)}\s*(.*?)\s*{re.escape(PROMPT_END)}", target, re.S)
        if not m:
            return empty
        return m.group(1).strip()

    # -- 会話履歴 ------------------------------------------------------------ #

    async def build_thread_messages(
        self, event: dict, client: AsyncWebClient
    ) -> Tuple[List[dict], Optional[str]]:
        """
        スレッド履歴を Agents SDK 向け messages[] 形式に変換し、
        直近 assistant の response_id も返す。

        * bot が files_upload_v2 で投稿した画像などの URL path も content に含める *
        """
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("event_ts")
        if not (channel and thread_ts):
            return [], None

        try:
            resp = await client.conversations_replies(
                channel=channel,
                ts=thread_ts,
                inclusive=True,
                limit=1000,
                include_all_metadata=True,
            )
            replies = sorted(resp["messages"], key=lambda m: float(m.get("ts", 0)))
        except Exception as exc:
            logger.warning(f"Failed to fetch thread replies: {exc}")
            return [], None

        history: List[dict] = []
        last_response_id: Optional[str] = None

        for m in replies:
            # ----------- 役割判定 ----------------------------------------- #
            role = (
                "assistant"
                if m.get("user") == self._bot_user_id or m.get("bot_id")
                else "user"
            )

            # ----------- テキスト部 --------------------------------------- #
            text = m.get("text", "") or ""
            if self._bot_user_id:
                mention_re = re.compile(
                    rf"<@{re.escape(self._bot_user_id)}(\|[^>]+)?>"
                )
                text = mention_re.sub("(AI アシスタントへ問い合わせ)", text).strip()

            # ----------- 添付ファイル (画像) -------------------------------- #
            file_paths: List[str] = []
            for f in m.get("files", []) or []:
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                parsed = urlparse(url)
                if parsed.path:  # 末尾にクエリが付くこともあるため path のみ
                    file_paths.append(parsed.path)

            # コンテンツが無いメッセージはスキップしない（画像のみなど）
            if text or file_paths:
                content_lines = []
                if text:
                    content_lines.append(text)
                for p in file_paths:
                    content_lines.append(f"添付ファイル: {p}")
                history.append({"role": role, "content": "\n".join(content_lines)})

        # ----------- 直近 assistant の response_id ------------------------ #
        for m in reversed(replies):
            md = m.get("metadata", {})
            if (
                md.get("event_type") == "agent_response"
                and "event_payload" in md
                and "response_id" in md["event_payload"]
            ):
                last_response_id = md["event_payload"]["response_id"]
                break

        return history, last_response_id

    def get_download_file_tool(self) -> Callable:
        """
        Slack の添付ファイルパスを受け取り、ダウンロード → 保存 →
        公開 URL を返す Tool (function-callable) を生成して返す。

        * 引数: slack_file_path : str 例) /files-pri/AAA/BBB/download/xxx.png
        * 返値: 保存後の外向き URL (str)
        """

        adapter = self  # クロージャに閉じ込め

        @function_tool
        async def slack_download_file(
            slack_file_path: Annotated[
                str,
                Field(
                    ...,
                    title="Slack file path",
                    description="例: /files-pri/Txxx-Fyyy/download/zzzz.png",
                ),
            ]
        ) -> str:
            """Download Slack file and return public URL"""
            full_url = f"https://files.slack.com{slack_file_path}"
            mime, raw = await adapter._download_image(full_url)
            rel = adapter._save_image(mime, raw)
            return f"{adapter.base_url}/static/{rel.as_posix()}"

        return slack_download_file
