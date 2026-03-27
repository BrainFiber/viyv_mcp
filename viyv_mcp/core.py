# core.py
"""ViyvMCP -- Streamable HTTP + 静的配信 + エントリー群を 1 つにまとめる ASGI アプリ"""
import logging

from starlette.applications import Starlette

from viyv_mcp.server import McpServer
from viyv_mcp.app.lifespan import app_lifespan_context
from viyv_mcp.app.bridge_manager import init_bridges, close_bridges, unregister_bridged_tools
from viyv_mcp.app.config import Config
from viyv_mcp.app.mcp_initialize_fix import monkey_patch_mcp_validation
from viyv_mcp.app.relay_mcp_handler import register_browser_tools_for_session
from viyv_mcp.app.mcp_factory import create_mcp_server
from viyv_mcp.app.asgi_builder import (
    ensure_static_dir,
    setup_ws_bridge,
    apply_security,
    build_routes,
)
from viyv_mcp.app.lifespan_composer import compose_lifespan

logger = logging.getLogger(__name__)


def _extract_lifespan(app):
    """Starlette app から lifespan context を安全に取得する。"""
    if app is None:
        return None
    try:
        return app.router.lifespan_context
    except AttributeError:
        return None


class ViyvMCP:
    """Streamable HTTP + 静的配信 + エントリー群を 1 つにまとめる ASGI アプリ"""

    def __init__(
        self,
        server_name: str = "My Streamable HTTP MCP Server",
        stateless_http: bool | None = None,
        bridge_config: str | None = None,
    ) -> None:
        monkey_patch_mcp_validation()

        self.server_name = server_name
        self.stateless_http = stateless_http
        self._bridge_config = bridge_config or Config.BRIDGE_CONFIG_DIR
        self._mcp: McpServer | None = None
        self._mcp_app = None
        self._relay_mcp: McpServer | None = None
        self._relay_mcp_app = None
        self._ws_bridge_hub = None
        self._ws_registered_tools: dict[str, list[str]] = {}
        self._bridges = None
        self._asgi_app = self._assemble()

    # --------------------------------------------------------------------- #
    #  WebSocket コールバック                                                 #
    # --------------------------------------------------------------------- #
    def _on_ws_connect(self, key: str, session):
        if not self._relay_mcp:
            logger.warning("[ws-bridge] Relay MCP not available, skipping tool registration")
            return
        tool_names = register_browser_tools_for_session(
            self._relay_mcp, session, tags={'browser', 'relay'},
        )
        self._ws_registered_tools[key] = tool_names
        logger.info(
            f"[ws-bridge:{session.key_prefix}] "
            f"Registered {len(tool_names)} browser tools on relay MCP"
        )

    def _on_ws_disconnect(self, key: str, session):
        tool_names = self._ws_registered_tools.pop(key, [])
        if tool_names and self._relay_mcp:
            unregister_bridged_tools(self._relay_mcp, tool_names)
            logger.info(
                f"[ws-bridge:{session.key_prefix}] "
                f"Unregistered {len(tool_names)} browser tools from relay MCP"
            )

    # --------------------------------------------------------------------- #
    #  ASGI アプリ組み立て                                                     #
    # --------------------------------------------------------------------- #
    def _assemble(self):
        # 1. MCP サーバー生成
        self._mcp = create_mcp_server(self.server_name, app_lifespan_context)
        self._mcp_app = self._mcp.http_app(
            path="/", stateless_http=self.stateless_http,
        )

        # 2. 静的ファイル
        static_dir = ensure_static_dir()

        # 3. WebSocket ブリッジ
        ws = setup_ws_bridge(
            self.server_name,
            self.stateless_http,
            on_connect=self._on_ws_connect,
            on_disconnect=self._on_ws_disconnect,
        )
        self._relay_mcp = ws.relay_mcp
        self._relay_mcp_app = ws.relay_mcp_app
        self._ws_bridge_hub = ws.ws_bridge_hub

        # 4. lifespan をセキュリティ適用前に取得
        mcp_lifespan = _extract_lifespan(self._mcp_app)
        relay_lifespan = _extract_lifespan(self._relay_mcp_app)

        # 5. セキュリティ
        self._mcp_app, self._relay_mcp_app = apply_security(
            self._mcp, self._mcp_app,
            self._relay_mcp, self._relay_mcp_app,
        )

        # 6. ブリッジ startup/shutdown
        bridge_config = self._bridge_config

        async def bridges_startup():
            logger.info("=== ViyvMCP startup: bridging external MCP servers ===")
            self._bridges = await init_bridges(self._mcp, bridge_config)

        async def bridges_shutdown():
            logger.info("=== ViyvMCP shutdown: closing external MCP servers ===")
            if self._bridges:
                await close_bridges(self._bridges)

        # 7. 複合 lifespan
        lifespan = compose_lifespan(
            mcp_lifespan=mcp_lifespan,
            relay_lifespan=relay_lifespan,
            bridges_startup=bridges_startup,
            bridges_shutdown=bridges_shutdown,
            ws_bridge_hub=self._ws_bridge_hub,
        )

        # 8. ルート + Starlette
        routes = build_routes(ws.ws_routes, static_dir)
        self._starlette_app = Starlette(routes=routes, lifespan=lifespan)

        return self

    # --------------------------------------------------------------------- #
    #  ASGI エントリポイント (HTTP)                                            #
    # --------------------------------------------------------------------- #
    def get_app(self):
        return self._asgi_app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        if path.startswith("/relay/mcp") and self._relay_mcp_app:
            new_path = path[10:] if len(path) > 10 else "/"
            scope = dict(scope)
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode()
            return await self._relay_mcp_app(scope, receive, send)

        if path.startswith("/mcp"):
            new_path = path[4:] if len(path) > 4 else "/"
            scope = dict(scope)
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode()
            return await self._mcp_app(scope, receive, send)

        return await self._starlette_app(scope, receive, send)

    # --------------------------------------------------------------------- #
    #  stdio エントリポイント                                                  #
    # --------------------------------------------------------------------- #
    async def run_stdio_async(self):
        """stdio transport で MCP サーバーを起動する。"""
        bridges = await init_bridges(self._mcp, self._bridge_config)
        try:
            await self._mcp.run_stdio_async()
        finally:
            if bridges:
                await close_bridges(bridges)
