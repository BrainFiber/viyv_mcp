# app/tools/image_generation_tools.py
"""
OpenAI Image-API tools for **viyv_mcp / FastMCP**

* generate_image   – gpt-image-1 で画像を生成し STATIC_DIR に保存して URL を返す
* edit_image       – gpt-image-1 で既存画像を編集 / インペイントし保存
* variation_image  – DALL·E 2 でバリエーションを生成し保存
"""

import base64
import io
import os
import pathlib
import uuid
import imghdr
from typing import Annotated, List, Literal, Optional, Sequence, Union

import aiohttp                          # ★★★ 追加
import openai
from pydantic import Field
from viyv_mcp import tool
from fastmcp import FastMCP  # 型ヒント用 (任意)

# ────────────────────────────── 環境設定 ────────────────────────────── #

STATIC_DIR = pathlib.Path(
    os.getenv("STATIC_DIR", os.path.join(os.getcwd(), "static", "images"))
)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.getenv("BASE_URL", "")  # 例: "https://example.com"

# ────────────────────────────── Helper 関数 ────────────────────────────── #


def _get_client() -> "openai.OpenAI":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    return openai.OpenAI(api_key=api_key)


def _strip_data_uri(b64_or_uri: str) -> str:
    if ";base64," in b64_or_uri:
        return b64_or_uri.split(";base64,", 1)[1]
    return b64_or_uri


def _b64_to_file(b64_or_uri: str, *, filename: Optional[str] = None) -> io.BytesIO:
    try:
        raw = base64.b64decode(_strip_data_uri(b64_or_uri), validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 image string") from exc

    detected_fmt = imghdr.what(None, raw) or "png"
    ext = {"jpeg": "jpg"}.get(detected_fmt, detected_fmt)

    bio = io.BytesIO(raw)
    bio.name = filename or f"upload.{ext}"
    bio.seek(0)
    return bio


async def _url_to_file(url: str, *, filename: Optional[str] = None) -> io.BytesIO:  # ★★★
    """
    URL から画像データを取得し file-like オブジェクトに変換（非同期）
    """
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, allow_redirects=True) as resp:
            resp.raise_for_status()
            data = await resp.read()

    detected_fmt = imghdr.what(None, data) or "png"
    ext = {"jpeg": "jpg"}.get(detected_fmt, detected_fmt)

    bio = io.BytesIO(data)
    bio.name = filename or f"upload.{ext}"
    bio.seek(0)
    return bio


def _save_bytes_and_get_url(data: bytes, *, ext: str = "png") -> str:
    fname = f"{uuid.uuid4()}.{ext}"
    (STATIC_DIR / fname).write_bytes(data)
    base_url = BASE_URL or "http://localhost:8000"
    return f"{base_url}/static/images/{fname}"


def _is_url(s: str) -> bool:  # ★★★
    return s.startswith("http://") or s.startswith("https://") or s.startswith("/static/")


# ────────────────────────────── Tool 登録 ────────────────────────────── #


def register(mcp: FastMCP):
    client = _get_client()

    # ------------------------------------------------------------------ #
    # 1) generate_image – gpt-image-1
    # ------------------------------------------------------------------ #
    @tool(
        description="テキストプロンプトから画像を生成し保存して URL を返す",
        tags={"image", "generation"},
    )
    async def generate_image(
        prompt: Annotated[str, Field(title="生成プロンプト", description="画像の内容を詳しく説明")],
        size: Annotated[
            Literal["1024x1024", "1536x1024", "1024x1536", "auto"], Field(default="1024x1024")
        ] = "1024x1024",
        quality: Annotated[
            Literal["low", "medium", "high", "auto"], Field(default="high")
        ] = "low",
        n: Annotated[int, Field(ge=1, le=4)] = 1,
        background: Annotated[
            Literal["transparent", "opaque", "auto"], Field(default="auto")
        ] = "auto",
        output_format: Annotated[
            Literal["png", "jpeg", "webp"], Field(default="png")
        ] = "png",
        moderation: Annotated[
            Literal["auto", "low"], Field(default="auto")
        ] = "auto",
    ) -> List[str]:
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size,
            quality=quality,
            n=n,
            background=background,
            output_format=output_format,
            moderation=moderation,
        )
        return [
            _save_bytes_and_get_url(base64.b64decode(img.b64_json), ext=output_format)
            for img in resp.data
        ]

    # ------------------------------------------------------------------ #
    # 2) edit_image – gpt-image-1
    # ------------------------------------------------------------------ #
    @tool(
        description="既存画像を gpt-image-1 で編集し保存して URL を返す",
        tags={"image", "edit"},
    )
    async def edit_image(
        prompt: Annotated[str, Field(title="編集プロンプト", description="編集後の画像内容")],
        image_b64: Annotated[  # 名称は維持。URL または base64 のどちらでも受け付ける   ★★★
            List[str],
            Field(
                title="ベース画像(URL or base64) – List[str]",
                description="`http(s)://` / `/static/...` の URL もしくは base64 文字列",
            ),
        ],
        mask_b64: Annotated[  # こちらも URL または base64 で受け付ける               ★★★
            Optional[str],
            Field(
                title="マスク画像(URL or base64) – αチャンネル必須（省略可）",
                description="`http(s)://` / `/static/...` の URL もしくは base64 文字列",
            ),
        ] = None,
        size: Annotated[
            Literal["1024x1024", "1536x1024", "1024x1536", "auto"],
            Field(default="auto"),
        ] = "auto",
        quality: Annotated[
            Literal["low", "medium", "high", "auto"], Field(default="auto")
        ] = "auto",
    ) -> List[str]:

        # --------- 入力画像を file-like オブジェクトへ変換 ----------------- ★★★
        async def _to_file_async(src: str) -> io.BytesIO:
            if _is_url(src):
                return await _url_to_file(src)
            return _b64_to_file(src)

        images: List[io.BytesIO] = []

        if isinstance(image_b64, str):
            images.append(await _to_file_async(image_b64))
        else:
            for itm in image_b64:
                images.append(await _to_file_async(itm))

        kwargs = dict(
            model="gpt-image-1",
            image=images,
            prompt=prompt,
            size=size,
            quality=quality,
        )

        if mask_b64:
            kwargs["mask"] = await _to_file_async(mask_b64)  # URL / base64 どちらでも

        resp = client.images.edit(**kwargs)  # type: ignore[arg-type]

        return [
            _save_bytes_and_get_url(base64.b64decode(img.b64_json), ext="png")
            for img in resp.data
        ]

    # ------------------------------------------------------------------ #
    # 3) variation_image – DALL·E 2
    # ------------------------------------------------------------------ #
    @tool(
        description="DALL·E 2 で画像のバリエーションを生成し保存",
        tags={"image", "variation"},
    )
    async def variation_image(
        image_b64: Annotated[str, Field(title="元画像(base64)")],
        n: Annotated[int, Field(ge=1, le=4)] = 1,
        size: Annotated[
            Literal["1024x1024", "1536x1024", "1024x1536"], Field(default="1024x1024")
        ] = "1024x1024",
        output_format: Annotated[
            Literal["png", "jpeg", "webp"], Field(default="png")
        ] = "png",
    ) -> List[str]:
        resp = client.images.variations(
            model="dall-e-2",
            image=_b64_to_file(image_b64),
            n=n,
            size=size,
            response_format="b64_json",
        )  # type: ignore[arg-type]

        return [
            _save_bytes_and_get_url(base64.b64decode(img.b64_json), ext=output_format)
            for img in resp.data
        ]