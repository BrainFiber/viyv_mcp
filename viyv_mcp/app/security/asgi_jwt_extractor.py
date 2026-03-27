"""Thin ASGI middleware that extracts JWT from the HTTP Authorization header
and stores the resulting :class:`AgentIdentity` in a :class:`ContextVar`.

This layer does **not** perform authorization — it only establishes identity.
The MCP protocol handlers in :class:`~viyv_mcp.server.mcp_server.McpServer`
handle all authorization decisions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from viyv_mcp.app.security.context import reset_agent_identity, set_agent_identity
from viyv_mcp.app.security.infrastructure.jwt_codec import JWTDecodeError, JWTExpiredError

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from viyv_mcp.app.security.service import SecurityService

logger = logging.getLogger(__name__)


class JWTExtractorMiddleware:
    """ASGI middleware: ``Authorization: Bearer <jwt>`` → ContextVar."""

    def __init__(self, app: ASGIApp, service: SecurityService) -> None:
        self.app = app
        self._service = service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            token = self._extract_bearer(scope.get("headers", []))
            if token:
                try:
                    identity = self._service.authenticate_token(token)
                    cv_token = set_agent_identity(identity)
                    try:
                        return await self.app(scope, receive, send)
                    finally:
                        reset_agent_identity(cv_token)
                except JWTExpiredError:
                    logger.debug("Security: JWT expired in HTTP request")
                except JWTDecodeError as exc:
                    logger.debug(f"Security: JWT decode failed — {exc}")
                # Fall through — identity stays None; MCP handler will deny

        await self.app(scope, receive, send)

    @staticmethod
    def _extract_bearer(headers: list[tuple[bytes, bytes]]) -> str | None:
        for key, value in headers:
            if key.lower() == b"authorization":
                parts = value.decode("latin-1").split(" ", 1)
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    return parts[1]
        return None
