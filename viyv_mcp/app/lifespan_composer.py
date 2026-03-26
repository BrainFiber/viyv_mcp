# lifespan_composer.py
"""複合 lifespan 管理。

MCP / Relay MCP / 外部ブリッジ / WebSocket セッションの
ネストされたライフサイクルを一つにまとめる。
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _noop_lifespan(app: Any):
    yield


def compose_lifespan(
    mcp_app: ASGIApp,
    relay_mcp_app: ASGIApp | None,
    bridges_startup: Callable[[], Awaitable[None]],
    bridges_shutdown: Callable[[], Awaitable[None]],
    ws_bridge_hub: Any | None,
) -> Callable:
    """MCP → Relay → Bridge → WS cleanup のネストされた lifespan を構築する。"""

    # MCP lifespan の取得
    try:
        mcp_lifespan = mcp_app.router.lifespan_context
    except AttributeError:
        logger.warning("MCP app router lifespan not found, using no-op")
        mcp_lifespan = _noop_lifespan

    # Relay MCP lifespan の取得
    relay_lifespan = None
    if relay_mcp_app:
        try:
            relay_lifespan = relay_mcp_app.router.lifespan_context
        except AttributeError:
            pass

    @asynccontextmanager
    async def lifespan(app: Any):
        # ① MCP 側の session/lifespan を起動
        async with mcp_lifespan(app):
            # ②  Relay MCP の lifespan も起動
            relay_ctx = relay_lifespan(app) if relay_lifespan else _noop_lifespan(app)
            async with relay_ctx:
                # ③ 外部ブリッジ起動
                await bridges_startup()
                try:
                    yield
                finally:
                    # ④ WebSocket セッション終了
                    if ws_bridge_hub:
                        for key, session in list(ws_bridge_hub.sessions.items()):
                            await session.close()
                        logger.info("ViyvMCP: WebSocket bridge sessions closed")
                    # ⑤ 外部ブリッジ終了
                    await bridges_shutdown()

    return lifespan
