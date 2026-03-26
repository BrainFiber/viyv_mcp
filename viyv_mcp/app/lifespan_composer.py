# lifespan_composer.py
"""複合 lifespan 管理。

MCP / Relay MCP / 外部ブリッジ / WebSocket セッションの
ネストされたライフサイクルを一つにまとめる。
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _noop_lifespan(app: Any):
    yield


def compose_lifespan(
    mcp_lifespan: Callable | None,
    relay_lifespan: Callable | None,
    bridges_startup: Callable[[], Awaitable[None]],
    bridges_shutdown: Callable[[], Awaitable[None]],
    ws_bridge_hub: Any | None,
) -> Callable:
    """MCP → Relay → Bridge → WS cleanup のネストされた lifespan を構築する。

    Parameters
    ----------
    mcp_lifespan : async context manager factory, or None
        FastMCP の StreamableHTTPSessionManager lifespan。
        ``mcp_http_app.router.lifespan_context`` から取得したものを渡す。
    relay_lifespan : same, or None
        Relay MCP 用。WS ブリッジ無効時は None。
    """
    _mcp_ls = mcp_lifespan or _noop_lifespan
    _relay_ls = relay_lifespan

    @asynccontextmanager
    async def lifespan(app: Any):
        # ① MCP 側の session/lifespan を起動
        async with _mcp_ls(app):
            # ② Relay MCP の lifespan も起動
            relay_ctx = _relay_ls(app) if _relay_ls else _noop_lifespan(app)
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
