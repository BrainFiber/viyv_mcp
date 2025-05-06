from typing import Annotated, List

from pydantic import Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools
import os, json, logging, openai

from agents import Runner, enable_verbose_stdout_logging

# ─── ログ設定 ────────────────────────────────────────────────────────────────
openai.log = "debug"                      # HTTP リクエスト／レスポンス全文
logging.basicConfig(level=logging.DEBUG)

try:
    from agents import Agent as OAAgent, Runner, enable_verbose_stdout_logging
except ImportError:                       # pragma: no cover
    raise RuntimeError(
        "Agents SDK がインストールされていません (`pip install openai-agents-python`)"
    )

enable_verbose_stdout_logging()           # SDK 内部ログを標準出力へ


@agent(
    name="vision_agent",
    description="ビジョンエージェントです。指示に従い、ビジョンを操作します。必ず指示を与えてください。",
)
async def vision_agent(
    instruction: Annotated[
        str,
        Field(
            title="ユーザーからの指示文（日本語可）",
            description="画像に対して実行したいことを示す指示。例: 「この画像に写っている動物を説明して」",
        ),
    ],
    images: Annotated[
        List[str],
        Field(
            title="Base64 エンコード済み画像データの配列",
            description="各要素は改行等を含まない Base64 文字列（プレフィックス不要）",
        ),
    ],
) -> str:

    """
    Parameters
    ----------
    instruction : str
        画像について何をしたいかを示すユーザー指示。例: 「この画像に写っている動物を説明して」
    images : List[str]
        画像を Base64 でエンコードした文字列のリスト。複数可。
    """

    # ─── 1) OAAgent 定義 ───────────────────────────────────────────────────
    agent_ = OAAgent(
        name="vision_agent",
        model="gpt-4o-mini",                          # Vision 対応モデル
        instructions=(
            "あなたはマルチモーダル AI アシスタントです。"
            "ユーザーから渡された画像（複数可）と指示内容を理解して、"
            "最適な回答を日本語で提供してください。"
            "必ず画像を考慮したうえで応答を生成してください。"
        ),
    )

    # ─── 2) Runner に渡すメッセージ構築 ─────────────────────────────────
    # `input` は “messages” に近い概念。Vision では content 配列に
    #  text / image の mixed payload を渡す【issue #159】  [oai_citation:0‡GitHub](https://github.com/openai/openai-agents-python/issues/159)
    content: list[dict] = [
        {"type": "input_text", "text": instruction},
    ]
    # 画像は data URI として渡す。ここでは PNG と決め打ち（必要なら変更可）
    content.extend(
        {
            "type": "input_image",
            "image_url": f"data:image/png;base64,{b64}",
        }
        for b64 in images
    )

    # ─── 3) 実行 ──────────────────────────────────────────────────────
    try:
        result = await Runner.run(
            agent_,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
        return str(result.final_output)
    except Exception as exc:                              # pragma: no cover
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"