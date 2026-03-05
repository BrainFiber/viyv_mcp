# core.py
import logging
import os
import pathlib
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.routing import Mount
from fastapi.staticfiles import StaticFiles

from fastmcp import FastMCP                       # ← FastMCP 3.1+
from viyv_mcp.app.lifespan import app_lifespan_context
from viyv_mcp.app.registry import auto_register_modules
from viyv_mcp.app.bridge_manager import init_bridges, close_bridges, unregister_bridged_tools
from viyv_mcp.app.config import Config
from viyv_mcp.app.entry_registry import list_entries
from viyv_mcp.app.mcp_initialize_fix import monkey_patch_mcp_validation
from viyv_mcp.app.ws_bridge import WebSocketBridgeHub, create_ws_bridge_app
from viyv_mcp.app.relay_key_manager import RelayKeyManager, create_key_api
from viyv_mcp.app.relay_mcp_handler import register_browser_tools_for_session

logger = logging.getLogger(__name__)


class ViyvMCP:
    """Streamable HTTP + 静的配信 + エントリー群を 1 つにまとめる ASGI アプリ"""

    def __init__(
        self,
        server_name: str = "My Streamable HTTP MCP Server",
        stateless_http: bool | None = None
    ) -> None:
        # MCP初期化の互換性パッチを適用
        monkey_patch_mcp_validation()

        self.server_name = server_name
        self.stateless_http = stateless_http
        self._mcp: FastMCP | None = None
        self._ws_bridge_hub: WebSocketBridgeHub | None = None
        self._ws_registered_tools: dict[str, list[str]] = {}  # key -> tool names
        self._asgi_app = self._create_asgi_app()
        self._bridges = None

    # --------------------------------------------------------------------- #
    #  FastMCP 本体                                                          #
    # --------------------------------------------------------------------- #
    def _create_mcp_server(self) -> FastMCP:
        """FastMCP を生成してローカル modules を自動登録"""
        mcp = FastMCP(self.server_name, lifespan=app_lifespan_context)

        auto_register_modules(mcp, "app.tools")
        auto_register_modules(mcp, "app.resources")
        auto_register_modules(mcp, "app.prompts")
        auto_register_modules(mcp, "app.agents")
        auto_register_modules(mcp, "app.entries")

        logger.info("ViyvMCP: MCP server created & local modules registered.")
        return mcp

    # --------------------------------------------------------------------- #
    #  Starlette アプリ組み立て                                               #
    # --------------------------------------------------------------------- #
    def _create_asgi_app(self):
        # --- MCP サブアプリ（Streamable HTTP） --------------------------- #
        self._mcp = self._create_mcp_server()
        # MCPアプリを生成（パスは / で、後でルーティング時に /mcp を処理）
        self._mcp_app = self._mcp.http_app(
            path="/",
            stateless_http=self.stateless_http
        )          # Streamable HTTP

        # --- 静的ファイル ------------------------------------------------- #
        STATIC_DIR = os.getenv(
            "STATIC_DIR",
            os.path.join(os.getcwd(), "static", "images"),
        )
        pathlib.Path(STATIC_DIR).mkdir(parents=True, exist_ok=True)

        # --- 外部 MCP ブリッジ ------------------------------------------- #
        async def bridges_startup():
            logger.info("=== ViyvMCP startup: bridging external MCP servers ===")
            self._bridges = await init_bridges(self._mcp, Config.BRIDGE_CONFIG_DIR)

        async def bridges_shutdown():
            logger.info("=== ViyvMCP shutdown: closing external MCP servers ===")
            if self._bridges:
                await close_bridges(self._bridges)

        # --- WebSocket ブリッジ --------------------------------------------- #
        if Config.WS_BRIDGE_ENABLED:
            key_manager = RelayKeyManager(
                ttl_hours=Config.RELAY_KEY_TTL_HOURS,
                storage_path=Config.RELAY_KEY_STORAGE,
            )

            def _on_ws_connect(key: str, session):
                """Register browser tools when Chrome extension connects."""
                tool_names = register_browser_tools_for_session(
                    self._mcp, session, tags={'browser', 'relay'},
                )
                self._ws_registered_tools[key] = tool_names
                logger.info(
                    f"[ws-bridge:{session.key_prefix}] "
                    f"Registered {len(tool_names)} browser tools on MCP"
                )

            def _on_ws_disconnect(key: str, session):
                """Unregister browser tools when Chrome extension disconnects."""
                tool_names = self._ws_registered_tools.pop(key, [])
                if tool_names:
                    unregister_bridged_tools(self._mcp, tool_names)
                    logger.info(
                        f"[ws-bridge:{session.key_prefix}] "
                        f"Unregistered {len(tool_names)} browser tools from MCP"
                    )

            self._ws_bridge_hub = WebSocketBridgeHub(
                key_manager,
                on_connect=_on_ws_connect,
                on_disconnect=_on_ws_disconnect,
            )
            ws_bridge_app = create_ws_bridge_app(self._ws_bridge_hub)
            logger.info("ViyvMCP: WebSocket bridge enabled")
        else:
            key_manager = None
            logger.info("ViyvMCP: WebSocket bridge disabled")

        # --- その他のルートのためのStarletteアプリ ------------------------- #
        routes = [
            Mount(path, app=factory() if callable(factory) else factory)
            for path, factory in list_entries()
        ]

        # WebSocket bridge routes
        if Config.WS_BRIDGE_ENABLED and key_manager:
            routes.append(Mount("/ws/bridge", app=ws_bridge_app))
            routes.append(Mount("/relay", routes=create_key_api(key_manager)))

        routes.append(
            Mount(
                "/static",
                app=StaticFiles(directory=os.path.dirname(STATIC_DIR), html=False),
                name="static",
            )
        )

        # --- 複合 lifespan ------------------------------------------------ #
        @asynccontextmanager
        async def _noop_lifespan(a):
            yield

        try:
            mcp_lifespan = self._mcp_app.router.lifespan_context
        except AttributeError:
            logger.warning("MCP app router lifespan not found, using no-op")
            mcp_lifespan = _noop_lifespan

        @asynccontextmanager
        async def lifespan(app):
            # ① MCP 側の session/lifespan を起動
            async with mcp_lifespan(app):
                # ② 外部ブリッジなど自前初期化
                await bridges_startup()
                try:
                    yield
                finally:
                    # Close all WS bridge sessions
                    if self._ws_bridge_hub:
                        for key, session in list(self._ws_bridge_hub.sessions.items()):
                            await session.close()
                        logger.info("ViyvMCP: WebSocket bridge sessions closed")
                    await bridges_shutdown()

        self._starlette_app = Starlette(routes=routes, lifespan=lifespan)

        # カスタムASGIルーターを返す
        return self

    # --------------------------------------------------------------------- #
    #  ASGI エントリポイント                                                 #
    # --------------------------------------------------------------------- #
    def get_app(self):
        return self._asgi_app

    async def __call__(self, scope, receive, send):
        """カスタムASGIルーター: /mcpパスを直接MCPアプリに、それ以外をStarletteに"""
        path = scope.get("path", "")

        # /mcp パスはMCPアプリに直接ルーティング（Starletteを経由しない）
        if path.startswith("/mcp"):
            # パスを調整: /mcp/xxx -> /xxx
            new_path = path[4:] if len(path) > 4 else "/"
            scope = dict(scope)
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode()
            return await self._mcp_app(scope, receive, send)
        else:
            # その他のパスはStarletteアプリに
            return await self._starlette_app(scope, receive, send)