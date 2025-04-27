# core.py
import logging
from starlette.applications import Starlette
from starlette.routing import Mount

from fastapi import FastAPI
from fastmcp import FastMCP

from viyv_mcp.app.lifespan import app_lifespan_context
from viyv_mcp.app.registry import auto_register_modules
from viyv_mcp.app.bridge_manager import init_bridges, close_bridges
from viyv_mcp.app.config import Config

logger = logging.getLogger(__name__)


class ViyvMCP:
    """SSE とヘルスチェックを 1 つの Starlette アプリで提供"""

    def __init__(self, server_name: str = "My SSE MCP Server") -> None:
        self.server_name = server_name
        self._mcp: FastMCP | None = None
        self._asgi_app = self._create_asgi_app()
        self._bridges = None

    # ---------- パーツ ---------- #

    @staticmethod
    def _create_health_app() -> FastAPI:
        """/health だけを返す FastAPI"""
        app = FastAPI()
        @app.get("/", include_in_schema=False)
        async def health_check():
            return {"status": "ok"}
        return app

    def _create_mcp_server(self) -> FastMCP:
        """FastMCP を生成し、ツール等を登録"""
        mcp = FastMCP(self.server_name, lifespan=app_lifespan_context)

        # 自動登録: プロジェクト構成に合わせてパスを調整
        auto_register_modules(mcp, "app.tools")
        auto_register_modules(mcp, "app.resources")
        auto_register_modules(mcp, "app.prompts")

        logger.info("ViyvMCP: MCP server created & local modules registered.")
        return mcp

    # ---------- Starlette 合成 ---------- #

    def _create_asgi_app(self):
        health_app = self._create_health_app()
        self._mcp = self._create_mcp_server()
        sse_subapp = self._mcp.sse_app()          # ← SSE・messages 用

        async def startup():
            logger.info("=== ViyvMCP startup: bridging external MCP servers ===")
            self._bridges = await init_bridges(self._mcp, Config.BRIDGE_CONFIG_DIR)

        async def shutdown():
            logger.info("=== ViyvMCP shutdown: closing external MCP servers ===")
            if self._bridges:
                await close_bridges(self._bridges)

        # `/health` を先に、`/` (SSE) を後に並べる
        app = Starlette(
            on_startup=[startup],
            on_shutdown=[shutdown],
            routes=[
                Mount("/health", app=health_app),   # → http://host:port/health
                Mount("/",        app=sse_subapp),  # → /sse, /messages/…
            ],
        )
        return app

    # ---------- ASGI エントリポイント ---------- #

    def get_app(self):
        return self._asgi_app

    def __call__(self, scope, receive, send):
        return self._asgi_app(scope, receive, send)