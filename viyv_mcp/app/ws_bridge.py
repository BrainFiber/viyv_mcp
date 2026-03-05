"""WebSocket bridge hub -- manages Chrome extension connections."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from viyv_mcp.app.ws_bridge_protocol import AuthResult, PongMessage
from viyv_mcp.app.ws_bridge_session import WebSocketBridgeSession
from viyv_mcp.app.relay_key_manager import RelayKeyManager

logger = logging.getLogger(__name__)


class WebSocketBridgeHub:
    """Manages WebSocket connections from Chrome extensions, keyed by relay key."""

    def __init__(
        self,
        key_manager: RelayKeyManager,
        on_connect: Callable[[str, WebSocketBridgeSession], None] | None = None,
        on_disconnect: Callable[[str, WebSocketBridgeSession], None] | None = None,
    ) -> None:
        self._key_manager = key_manager
        # key -> session
        self._sessions: dict[str, WebSocketBridgeSession] = {}
        self._lock = asyncio.Lock()
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    def get_session(self, key: str) -> WebSocketBridgeSession | None:
        return self._sessions.get(key)

    @property
    def sessions(self) -> dict[str, WebSocketBridgeSession]:
        return self._sessions

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection from a Chrome extension."""
        await websocket.accept()
        session: WebSocketBridgeSession | None = None
        key: str | None = None

        try:
            # First message must be auth
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    AuthResult(
                        success=False, error='Invalid JSON'
                    ).model_dump()
                )
                await websocket.close(1008, 'Invalid JSON')
                return

            if data.get('type') != 'auth' or not data.get('key'):
                await websocket.send_json(
                    AuthResult(
                        success=False, error='First message must be auth with key'
                    ).model_dump()
                )
                await websocket.close(1008, 'Authentication required')
                return

            key = data['key']
            key_prefix = key[:8] if len(key) >= 8 else key

            # Validate key
            if not self._key_manager.validate_key(key):
                logger.warning(f"[ws-bridge] Invalid key: {key_prefix}...")
                await websocket.send_json(
                    AuthResult(
                        success=False, error='Invalid or expired key'
                    ).model_dump()
                )
                await websocket.close(1008, 'Invalid key')
                return

            # Check 1-key-1-connection
            async with self._lock:
                if key in self._sessions:
                    logger.warning(
                        f"[ws-bridge:{key_prefix}] Key already connected, rejecting"
                    )
                    await websocket.send_json(
                        AuthResult(
                            success=False,
                            error='Key already in use by another connection',
                        ).model_dump()
                    )
                    await websocket.close(1008, 'Key in use')
                    return

                session = WebSocketBridgeSession(websocket, key)
                self._sessions[key] = session

            logger.info(f"[ws-bridge:{key_prefix}] Chrome extension connected")
            await websocket.send_json(AuthResult(success=True).model_dump())

            # Notify connection callback
            if self._on_connect and session:
                try:
                    self._on_connect(key, session)
                except Exception as e:
                    logger.error(f"[ws-bridge:{key_prefix}] on_connect callback error: {e}")

            # Message loop
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"[ws-bridge:{key_prefix}] Invalid JSON, ignoring")
                    continue
                msg_type = data.get('type')

                if msg_type == 'pong':
                    continue
                elif msg_type == 'ping':
                    await websocket.send_json(PongMessage().model_dump())
                elif msg_type == 'tool_result':
                    session.handle_message(data)
                else:
                    logger.debug(
                        f"[ws-bridge:{key_prefix}] Unknown message type: {msg_type}"
                    )

        except WebSocketDisconnect:
            if key:
                key_prefix = key[:8] if len(key) >= 8 else key
                logger.info(
                    f"[ws-bridge:{key_prefix}] Chrome extension disconnected"
                )
        except asyncio.TimeoutError:
            logger.warning("[ws-bridge] Auth timeout -- closing connection")
            try:
                await websocket.close(1008, 'Auth timeout')
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[ws-bridge] WebSocket error: {e}")
        finally:
            if key and session:
                # Notify disconnection callback
                if self._on_disconnect:
                    try:
                        self._on_disconnect(key, session)
                    except Exception as e:
                        logger.error(f"[ws-bridge] on_disconnect callback error: {e}")
                async with self._lock:
                    self._sessions.pop(key, None)
                await session.close()


def create_ws_bridge_app(
    hub: WebSocketBridgeHub,
) -> Starlette:
    """Create a Starlette sub-app for WebSocket bridge endpoints."""

    async def ws_bridge_endpoint(websocket: WebSocket) -> None:
        await hub.handle_websocket(websocket)

    async def bridge_status(request: Request) -> JSONResponse:
        """GET /status -- show connected keys (prefixed) and count."""
        keys = [k[:8] + '...' for k in hub.sessions.keys()]
        return JSONResponse({
            'connected': len(keys),
            'keys': keys,
        })

    routes = [
        WebSocketRoute('/', ws_bridge_endpoint),
        Route('/status', bridge_status, methods=['GET']),
    ]

    return Starlette(routes=routes)
