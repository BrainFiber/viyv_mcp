# asgi_builder.py
"""ASGI アプリ構築のためのユーティリティ群。

* 静的ファイルディレクトリの確保
* WebSocket ブリッジのセットアップ
* セキュリティレイヤーの適用
* Starlette ルートの組み立て
"""
import logging
import os
import pathlib
from typing import Any, Callable, NamedTuple

from viyv_mcp.server import McpServer
from starlette.routing import Mount
from starlette.types import ASGIApp
from fastapi.staticfiles import StaticFiles

from viyv_mcp.app.config import Config
from viyv_mcp.app.entry_registry import list_entries
from viyv_mcp.app.ws_bridge import WebSocketBridgeHub, create_ws_bridge_app
from viyv_mcp.app.relay_key_manager import RelayKeyManager, create_key_api

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# 戻り値型                                                                     #
# --------------------------------------------------------------------------- #
class WSBridgeComponents(NamedTuple):
    relay_mcp: McpServer | None
    relay_mcp_app: ASGIApp | None
    ws_bridge_hub: WebSocketBridgeHub | None
    ws_routes: list
    key_manager: RelayKeyManager | None


# --------------------------------------------------------------------------- #
# 静的ファイル                                                                  #
# --------------------------------------------------------------------------- #
def ensure_static_dir() -> str:
    static_dir = os.getenv(
        "STATIC_DIR",
        os.path.join(os.getcwd(), "static", "images"),
    )
    pathlib.Path(static_dir).mkdir(parents=True, exist_ok=True)
    return static_dir


# --------------------------------------------------------------------------- #
# WebSocket ブリッジ                                                            #
# --------------------------------------------------------------------------- #
def setup_ws_bridge(
    server_name: str,
    stateless_http: bool | None,
    on_connect: Callable | None = None,
    on_disconnect: Callable | None = None,
) -> WSBridgeComponents:
    if not Config.WS_BRIDGE_ENABLED:
        logger.info("ViyvMCP: WebSocket bridge disabled")
        return WSBridgeComponents(None, None, None, [], None)

    key_manager = RelayKeyManager(
        ttl_hours=Config.RELAY_KEY_TTL_HOURS,
        storage_path=Config.RELAY_KEY_STORAGE,
    )

    relay_mcp = McpServer(f"{server_name} (Relay)")
    relay_mcp_app = relay_mcp.http_app(path="/", stateless_http=stateless_http)

    hub = WebSocketBridgeHub(
        key_manager,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
    )
    ws_app = create_ws_bridge_app(hub)

    ws_routes = [
        Mount("/ws/bridge", app=ws_app),
        Mount("/relay", routes=create_key_api(key_manager)),
    ]

    logger.info("ViyvMCP: WebSocket bridge enabled (relay MCP at /relay/mcp)")
    return WSBridgeComponents(relay_mcp, relay_mcp_app, hub, ws_routes, key_manager)


# --------------------------------------------------------------------------- #
# セキュリティレイヤー                                                          #
# --------------------------------------------------------------------------- #
def apply_security(
    mcp: McpServer,
    mcp_app: ASGIApp,
    relay_mcp: McpServer | None,
    relay_mcp_app: ASGIApp | None,
) -> tuple[ASGIApp, ASGIApp | None]:
    """セキュリティレイヤーを適用し、(wrapped_mcp_app, wrapped_relay_app) を返す。"""
    try:
        from viyv_mcp.app.security import create_security_layer
    except ImportError:
        logger.info("ViyvMCP: Security module not installed — running without security")
        return mcp_app, relay_mcp_app

    try:
        security = create_security_layer(tool_registry=mcp.registry)
    except SystemExit:
        raise
    except Exception as exc:
        logger.error(f"ViyvMCP: Security layer initialization FAILED — {exc}")
        raise

    if security:
        # Inject security service into MCP servers (handler-level checks)
        mcp.set_security_service(security.service)
        if relay_mcp:
            relay_mcp.set_security_service(security.service)

        # Wrap ASGI apps for HTTP JWT extraction
        mcp_app = security.wrap_asgi(mcp_app)
        if relay_mcp_app:
            relay_mcp_app = security.wrap_asgi(relay_mcp_app)

        logger.info("ViyvMCP: Security layer active")

    return mcp_app, relay_mcp_app


# --------------------------------------------------------------------------- #
# ルート組み立て                                                                #
# --------------------------------------------------------------------------- #
def build_routes(
    ws_routes: list,
    static_dir: str,
) -> list:
    routes = [
        Mount(path, app=factory() if callable(factory) else factory)
        for path, factory in list_entries()
    ]

    routes.extend(ws_routes)

    routes.append(
        Mount(
            "/static",
            app=StaticFiles(directory=os.path.dirname(static_dir), html=False),
            name="static",
        )
    )

    return routes
