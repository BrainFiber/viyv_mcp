from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan_context(app):
    # app: McpServer の low-level Server インスタンス
    lifespan_context = {"db": "dummy_db_connection"}
    try:
        yield lifespan_context
    finally:
        pass