from typing import Annotated, Optional

from pydantic import Field
from viyv_mcp import agent
from viyv_mcp.openai_bridge import build_function_tools


@agent(
    name="slack_agent",
    description="""
    Slack ワークスペースを操作するエージェントです。

    以下の操作が実行可能です：
    - slack_add_reaction: 指定したメッセージにリアクションを追加します。
    - slack_get_users: ワークスペース内のユーザー一覧を取得します。
    - slack_list_channels: ワークスペース内のチャンネル一覧を取得します。
    - slack_get_user_profile: 指定したユーザーのプロフィール情報を取得します。

    action に上記の操作名を、必要に応じて text にメッセージ本文やパラメータを指定してください。
""",
    use_tags=["slack"],  # Slack 関連ツールのみ登録
)
async def slack_agent(
    action: Annotated[
        str,
        Field(
            title="Slack アクション (自由入力)",
            description=(
                "実行する Slack 操作を文字列で指定してください "
                "例: post_message, list_channels, get_thread_history …"
            ),
        ),
    ],
    text: Annotated[
        Optional[str],
        Field(
            title="メッセージ本文",
            description="投稿 / 返信など本文が必要な操作で使用します。",
        ),
    ] = None,
    user_id: Annotated[
        Optional[str],
        Field(
            title="問い合わせユーザID",
            description="操作を実行したユーザの Slack ユーザID を指定してください。",
        ),
    ] = None,
    channel_id: Annotated[
        Optional[str],
        Field(
            title="チャンネルID",
            description="操作を実行するチャンネルの Slack チャンネルID を指定してください。",
        ),
    ] = None,
    thread_ts: Annotated[
        Optional[str],
        Field(
            title="スレッドのタイムスタンプ",
            description="スレッドに返信する場合は、スレッドのタイムスタンプを指定してください。",
        ),
    ] = None,
) -> str:

    # ① Slack 系 FunctionTool をすべて読み込む ----------------------------
    oa_tools = build_function_tools(
        exclude_tools=[
            "slack_post_message",
            "slack_get_thread_replies",
            "slack_get_channel_history",
        ]
    )

    # ② 内部エージェント定義 ---------------------------------------------
    try:
        from agents import Agent as OAAgent, Runner
    except ImportError:
        return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

    agent_ = OAAgent(
        name="SlackAssistant",
        instructions=(
            "あなたは Slack ワークスペースを操作する AI アシスタントです。\n"
            "利用可能なツールを必ず呼び出し、ユーザーの要求を正確に実行してください。"
        ),
        model="o4-mini-2025-04-16",
        tools=oa_tools,
    )

    # ③ LLM への入力メッセージを組み立て ----------------------------------
    user_message = f"Action: {action}\nText: {text}\nUser ID: {user_id}\nThread TS: {thread_ts}\nChannel ID: {channel_id}\n"

    # ④ 実行 --------------------------------------------------------------
    try:
        result = await Runner.run(agent_, user_message)
        return str(result.final_output)
    except Exception as exc:
        return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"
