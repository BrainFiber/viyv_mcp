from fastapi import FastAPI
from viyv_mcp.decorators import entry

@entry("/health")
def health_app() -> FastAPI:
    app = FastAPI()
    @app.get("/", include_in_schema=False)
    async def ping():
        return {"status": "ok"}
    return app

