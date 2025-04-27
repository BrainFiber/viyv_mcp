from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan_context(app):
    # app: FastMCP インスタンス（必要に応じて利用可能）
    print("サーバー起動：依存リソースの初期化を実施")
    lifespan_context = {"db": "dummy_db_connection"}
    try:
        yield lifespan_context
    finally:
        print("サーバー終了：依存リソースのクリーンアップを実施")