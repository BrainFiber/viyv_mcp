from fastapi import FastAPI
from viyv_mcp.decorators import entry
from viyv_mcp.openai_bridge import build_function_tools

@entry("/webhook", use_tags=["calc"])
def webhook_app() -> FastAPI:
    app = FastAPI()
    @app.get("/", include_in_schema=False)
    async def ping():

        # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
        oa_tools = build_function_tools(use_tools=["add"])

        # --- ③ エージェント定義 ----------------------------------------------
        try:
            from agents import Agent as OAAgent, Runner
        except ImportError:
            return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

        agent_ = OAAgent(
            name="Calculator",
            instructions=(
                "あなたは電卓として振る舞う AI アシスタントです。"
                "与えられた式を計算し、結果のみを日本語で簡潔に答えてください。必ず適切なtoolを使用してください。"
            ),
            model="o3-mini",
            tools=oa_tools,
        )

        # --- ④ 実行 ----------------------------------------------------------
        try:
            result = await Runner.run(agent_, f"1 + 2 を計算してください")
            return {"status": "success", "result": str(result.final_output)}
        except Exception as exc:
            return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"

    return app

@entry("/webhook/slack", use_tags=["slack"])
def webhook_app() -> FastAPI:
    app = FastAPI()
    @app.get("/", include_in_schema=False)
    async def ping():

        # --- ② OpenAI Agents SDK の Tool に変換 -------------------------------
        oa_tools = build_function_tools()

        # --- ③ エージェント定義 ----------------------------------------------
        try:
            from agents import Agent as OAAgent, Runner
        except ImportError:
            return "Agents SDK がインストールされていません (`pip install openai-agents-python`)"

        agent_ = OAAgent(
            name="Calculator",
            instructions=(
                "あなたはslackを管理する AI アシスタントです。"
                "toolを使って、slack チャンネル一覧を取得してください。"
            ),
            model="o3-mini",
            tools=oa_tools,
        )

        # --- ④ 実行 ----------------------------------------------------------
        try:
            result = await Runner.run(agent_, f"slack チャンネル一覧を取得してください")
            return {"status": "success", "result": str(result.final_output)}
        except Exception as exc:
            return f"ChatGPT への問い合わせでエラーが発生しました: {exc}"

    return app
