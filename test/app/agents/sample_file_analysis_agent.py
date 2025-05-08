# app/agents/file_agent.py
"""
任意ファイル（PDF / Office / テキスト / 画像 など）を LLM に渡して
内容を分析・要約・抽出するエージェント。

Slack などで保存した `/static/upload/...` の公開 URL を **複数** 受け取り、
OpenAI File API にアップロードしてから ChatCompletion に添付します。
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Annotated, List
from urllib.parse import unquote, urlparse

import aiohttp
from pydantic import BaseModel, Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools


@agent(
    name="file_analysis_agent",
    description="""
    ファイル（PDF・Office 文書・テキスト・画像など）を解析するエージェントです。
    解析したいファイルの公開 URL（複数可）と、どのように分析／要約してほしいかの
    指示（analysis_prompt）を渡してください。
    """,
    use_tags=["none"],
)
async def file_analysis_agent(
    file_urls: Annotated[
        List[str],
        Field(
            title="解析対象ファイルの URL 一覧",
            description="例: ['http://localhost:8000/static/upload/xxx.pdf', ...]",
        ),
    ],
    analysis_prompt: Annotated[
        str,
        Field(
            title="ファイルへ行う分析内容の指示",
            description="例: “これらの PDF を比較して要約して” など",
        ),
    ],
) -> str:

    # ------------ ① ファイルを並列ダウンロード ----------------------- #
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

    download_tasks = [_download(u) for u in file_urls]
    try:
        raw_files: List[bytes] = await asyncio.gather(*download_tasks)
    except Exception as exc:
        return f"ファイルのダウンロードに失敗しました: {exc!s}"

    # ------------ ② OpenAI File API へアップロード -------------------- #
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()

        async def _upload(raw: bytes, filename: str):
            # ――― 拡張子を維持した一時ファイルを生成 ――― #
            ext = os.path.splitext(filename)[1]  # 例: ".pdf" / ".xlsx"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(raw)
                tmp.flush()

                file_obj = await client.files.create(
                    file=open(tmp.name, "rb"),  # type: ignore[arg-type]
                    purpose="user_data",
                )

            return file_obj.id, filename

        filenames = [
            (os.path.basename(unquote(urlparse(u).path)) or f"file_{idx+1}")
            for idx, u in enumerate(file_urls)
        ]
        upload_tasks = [_upload(raw, fname) for raw, fname in zip(raw_files, filenames)]
        file_infos = await asyncio.gather(*upload_tasks)  # [(file_id, filename), ...]
    except Exception as exc:
        return f"OpenAI File API へのアップロードでエラーが発生しました: {exc!s}"

    if not file_infos:
        return "いずれのファイルもアップロードできませんでした。"

    # ------------ ③ OAAgent を構築して messages を渡す --------------- #
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    class Response(BaseModel):
        text: str = Field(..., title="解析結果")

    oa_tools = build_function_tools()

    analysis_agent = OAAgent(
        name="FileAnalysisAssistant",
        model="o4-mini-2025-04-16",
        instructions=(
            "あなたはアップロードされた複数ファイルを読み取り、"
            "ユーザーの analysis_prompt に従って分析・要約・抽出を行うアシスタントです。"
            f"{analysis_prompt}\n"
        ),
        tools=oa_tools,
        output_type=Response,
    )

    # --- file_contents を ResponseInputFileParam 形式で作成 -----------
    file_contents = [
        {
            "type": "input_file",
            "file_id": fid,
        }
        for fid, _ in file_infos
    ]

    messages = [{"role": "user", "content": file_contents}]

    # ------------ ④ 実行 & 結果を返す -------------------------------- #
    try:
        result = await Runner.run(analysis_agent, messages)
        return result.final_output.text
    except Exception as exc:
        return f"ファイル解析時にエラーが発生しました: {exc!s}"