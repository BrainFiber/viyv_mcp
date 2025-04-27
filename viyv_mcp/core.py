import logging
from starlette.applications import Starlette
from starlette.routing import Mount

from fastmcp import FastMCP

# 下記はプロジェクト内にあるモジュールをインポート（例: app/ 下）
# 実際のパッケージ構成に合わせて import パスを修正してください
from viyv_mcp.app.lifespan import app_lifespan_context
from viyv_mcp.app.registry import auto_register_modules
from viyv_mcp.app.bridge_manager import init_bridges, close_bridges
from viyv_mcp.app.config import Config

logger = logging.getLogger(__name__)

class ViyvMCP:
    """
    server.py の機能 (自動登録, ブリッジ, ライフスパンなど) を
    1つのクラスに集約したASGIアプリラッパ。
    """

    def __init__(self, server_name: str = "My SSE MCP Server"):
        self.server_name = server_name
        self._mcp = None
        self._asgi_app = self._create_asgi_app()
        self._bridges = None  # 外部MCPサーバーセッションを格納する

    def _create_mcp_server(self) -> FastMCP:
        """
        FastMCPインスタンスを生成し、ライフスパン＆自動登録をセットアップ。
        """
        # lifespan.pyのコンテキストを設定
        mcp = FastMCP(self.server_name, lifespan=app_lifespan_context)

        # registry.py による自動登録
        auto_register_modules(mcp, "app.tools")
        auto_register_modules(mcp, "app.resources")
        auto_register_modules(mcp, "app.prompts")

        logger.info("ViyvMCP: Created MCP server & auto-registered local modules.")
        return mcp

    def _create_asgi_app(self):
        """
        Starletteアプリを生成し、on_startup/on_shutdownで外部ブリッジを管理。
        """
        self._mcp = self._create_mcp_server()
        sse_subapp = self._mcp.sse_app()

        # 起動時に外部MCPサーバーをブリッジ
        async def startup():
            logger.info("=== ViyvMCP startup: bridging external MCP servers ===")
            # Config.BRIDGE_CONFIG_DIR を見て、.json設定を読み込みブリッジ開始
            self._bridges = await init_bridges(self._mcp, Config.BRIDGE_CONFIG_DIR)

        # 終了時に外部MCPサーバーをシャットダウン
        async def shutdown():
            logger.info("=== ViyvMCP shutdown: closing external MCP servers ===")
            if self._bridges is not None:
                await close_bridges(self._bridges)

        # StarletteにSSEサブアプリをマウント
        app = Starlette(
            on_startup=[startup],
            on_shutdown=[shutdown],
            routes=[
                Mount("/", app=sse_subapp),
            ],
        )
        return app
    
    def get_app(self):
        """
        ASGIアプリを取得するためのメソッド。
        これを使って、外部からASGIアプリにアクセスできるようにする。
        """
        if self._asgi_app is None:
            self._asgi_app = self._create_asgi_app()
        return self._asgi_app
    

    def __call__(self, scope, receive, send):
        """
        ASGIエントリポイント。
        uvicornなどのASGIサーバーが本クラスのインスタンスを呼び出す。
        """
        if self._asgi_app is None:
            self._asgi_app = self._create_asgi_app()
        return self._asgi_app(scope, receive, send)