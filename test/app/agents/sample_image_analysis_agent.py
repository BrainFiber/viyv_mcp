# app/agents/image_analysis_agent.py
"""
画像（PNG / JPEG / WEBP / GIF〈静止画〉）を LLM に渡して解析・要約・説明を行うエージェント。

Slack などで保存した `/static/upload/...` の公開 URL を **複数** 受け取り、
Base64 データ URI として ChatCompletion に添付します。
"""

import asyncio
import base64
import imghdr
import os
from pathlib import Path
from typing import Annotated, List
from urllib.parse import unquote, urlparse

import aiohttp
from pydantic import BaseModel, Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools


# OpenAI Vision 入力要件
_ALLOWED_MIME = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",   # 非アニメ GIF
    "webp": "image/webp",
}
_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


@agent(
    name="image_analysis_agent",
    description="""
    画像を解析するエージェントです。
    解析したい画像の公開 URL（複数可）と、どのように分析してほしいかの
    指示（analysis_prompt）を渡してください。
    """,
    use_tags=["none"],
)
async def image_analysis_agent(
    image_urls: Annotated[
        List[str],
        Field(
            title="解析対象画像の URL 一覧",
            description="例: ['http://localhost:8000/static/upload/xxx.jpg', ...]",
            min_items=1,
        ),
    ],
    analysis_prompt: Annotated[
        str,
        Field(
            title="画像へ行う分析内容の指示",
            description="例: “これらの画像の共通点を教えて” など",
        ),
    ],
) -> str:
    # ------------ ① 画像を並列ダウンロード ＆ 検証 ------------------- #
    async def _download(url: str) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, allow_redirects=True) as resp:
                    resp.raise_for_status()
                    return await resp.read()
        # file:// や相対パス
        p = Path(unquote(parsed.path))
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        return p.read_bytes()

    download_tasks = [_download(u) for u in image_urls]
    try:
        raw_images: List[bytes] = await asyncio.gather(*download_tasks)
    except Exception as exc:
        return f"画像のダウンロードに失敗しました: {exc!s}"

    data_uris: List[str] = []
    for idx, raw in enumerate(raw_images):
        if len(raw) > _MAX_BYTES:
            return f"{idx+1} 枚目の画像が 20 MB を超えています。"

        fmt = imghdr.what(None, raw)
        mime = _ALLOWED_MIME.get(fmt)
        if not mime:
            return f"{idx+1} 枚目の画像フォーマット ({fmt}) はサポート外です。"

        b64 = base64.b64encode(raw).decode()
        data_uris.append(f"data:{mime};base64,{b64}")

    # ------------ ② OAAgent を構築 & messages 生成 ------------------ #
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    class Response(BaseModel):
        text: str = Field(..., title="解析結果")

    oa_tools = build_function_tools()

    vision_agent = OAAgent(
        name="ImageAnalysisAssistant",
        model="o4-mini-2025-04-16",
        instructions=(
            "あなたはアップロードされた複数画像を読み取り、"
            "ユーザーの analysis_prompt に従って解析・要約・説明を行うアシスタントです。"
            f"{analysis_prompt}\n"
        ),
        tools=oa_tools,
        output_type=Response,
    )

    # ChatCompletion input 形式
    content_items = [
        {
            "type": "input_image",
            "image_url": uri,
        }
        for uri in data_uris
    ]
    messages = [{"role": "user", "content": content_items}]

    # ------------ ③ 実行 & 結果を返す ------------------------------- #
    try:
        result = await Runner.run(vision_agent, messages)
        return result.final_output.text
    except Exception as exc:
        return f"画像解析時にエラーが発生しました: {exc!s}"