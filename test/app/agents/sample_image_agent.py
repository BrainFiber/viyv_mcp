# app/agents/image_agent.py
from typing import Annotated, Optional, Literal, List

from pydantic import BaseModel, Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools


@agent(
    name="image_agent",
    description="""
    画像を生成・編集・バリエーション作成するエージェントです。

    利用可能な操作:
    - generate_image   : テキストプロンプトから新しい画像を生成
    - edit_image       : 元画像から新しい画像の作成 / 既存の画像を編集 / インペイント で利用する。
    - variation_image  : 画像のバリエーションを生成（DALL·E 2）

    **operation** に上記いずれかを指定し、必要なパラメータを入力してください。
    """,
    use_tags=["image"],
)
async def image_agent(
    operation: Annotated[
        str,
        Field(title="実行する画像操作(generate_image or edit_image or variation_image)", description="生成・編集・バリエーションから選択"),
    ],
    prompt: Annotated[
        str,
        Field(
            title="プロンプト 生成・編集したい内容を自然言語で記述（必須: generate / edit）",
            description="生成・編集したい内容を自然言語で記述（必須: generate / edit）",
        ),
    ] = None,
    image_url: Annotated[                                   # ★★★ param 名変更
        Optional[str],
        Field(
            title="ベース画像 URL を設定する",                 # ★★★
            description="編集・バリエーション元の画像（PNG/JPEG/WebP）を `/static/upload/...` などの URL で渡す",  # ★★★
        ),
    ] = None,
    mask_b64: Annotated[
        Optional[str],
        Field(
            title="マスク画像(base64) インペイント時に透明部分を置換するマスク（省略可）",
            description="インペイント時に透明部分を置換するマスク（省略可）",
        ),
    ] = None,
    n: Annotated[
        Optional[int],
        Field(
            title="生成枚数 生成 / バリエーション時に何枚出力するか（省略可） 1~4",
            ge=1,
            le=4,
            description="生成 / バリエーション時に何枚出力するか（省略可）",
        ),
    ] = 1,
    size: Annotated[
        Optional[str],
        Field(
            title="画像サイズ 1024x1024 / 1024x1536 / 1536x1024 / auto など（省略可）",
            description="1024x1024 / 1024x1536 / 1536x1024 / auto など（省略可）",
        ),
    ] = "1024x1024",
    quality: Annotated[
        Optional[str],
        Field(
            title="品質 low / medium / high / auto（省略可）※コスト削減のため low を指定してください。",
            description="low / medium / high / auto（省略可）",
        ),
    ] = "auto",
    background: Annotated[
        Optional[str],
        Field(
            title="背景 transparent / opaque / auto（省略可・gpt-image-1 のみ）",
            description="transparent / opaque / auto（省略可・gpt-image-1 のみ）",
        ),
    ] = "auto",
    response_format: Annotated[
        Optional[Literal["b64_json", "url"]],
        Field(
            title="レスポンス形式 DALL·E 系のみ url 指定可。gpt-image-1 は常に b64_json。",
            description="DALL·E 系のみ url 指定可。gpt-image-1 は常に b64_json。",
        ),
    ] = "b64_json",
) -> str | List[str]:

    oa_tools = build_function_tools()

    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"
    
    class Response(BaseModel):
        text: str = Field(..., title="返信メッセージ本文")
        image_urls: Optional[List[str]] = Field(None, title="画像 URLs")

    agent_ = OAAgent(
        name="ImageAssistant",
        instructions=(
            "あなたは画像生成・編集を行うアシスタントです。\n"
            "ユーザーの要求を満たすために、必ず適切な画像ツールを呼び出してください。"
        ),
        model="o4-mini-2025-04-16",
        tools=oa_tools,
        output_type=Response
    )

    # ③ LLM へ渡すメッセージを整形
    user_message = (
        f"Operation: {operation}\n"
        f"Prompt: {prompt}\n"
        f"Image_url: {image_url if image_url else None}\n"       # ★★★
        f"Mask_b64: {mask_b64 if mask_b64 else None}\n"
        f"n: {n}\n"
        f"size: {size}\n"
        f"quality: {quality}\n"
        f"background: {background}\n"
        f"response_format: {response_format}"
    )

    try:
        result = await Runner.run(agent_, user_message)
        return result.final_output
    except Exception as exc:
        return f"画像エージェント実行時にエラーが発生しました: {exc}"