"""Security subsystem — Composition Root.

Call :func:`create_security_layer` from ``asgi_builder.py`` to initialise
the entire security stack.  Returns ``None`` in bypass mode (zero overhead
for existing users).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from viyv_mcp.app.security.context import set_agent_identity
from viyv_mcp.app.security.domain.models import AuthMode, ToolMetadataProvider
from viyv_mcp.app.security.infrastructure.audit_writer import setup_audit_logger
from viyv_mcp.app.security.infrastructure.config_loader import (
    SecurityConfig,
    load_security_config,
    validate_config,
)
from viyv_mcp.app.security.service import SecurityService

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SecurityLayer:
    """Facade returned by :func:`create_security_layer`."""

    def __init__(self, service: SecurityService) -> None:
        self.service = service

    def wrap_asgi(self, app: ASGIApp) -> ASGIApp:
        """Wrap *app* with the JWT-extracting ASGI layer (HTTP only)."""
        from viyv_mcp.app.security.asgi_jwt_extractor import JWTExtractorMiddleware

        return JWTExtractorMiddleware(app, self.service)


def create_security_layer(
    tool_registry: ToolMetadataProvider | None = None,
) -> SecurityLayer | None:
    """Bootstrap the entire security subsystem.

    *tool_registry* should be an :class:`McpRegistry` that implements
    :class:`ToolMetadataProvider`.  Security metadata is queried from the
    live tool registry at authorization time.

    Returns ``None`` when running in **bypass** mode.
    """

    # 1. Load & validate config
    config = load_security_config()
    validate_config(config)

    # 2. Bypass -> early exit
    if config.auth_mode == AuthMode.BYPASS:
        logger.warning(
            "\u26a0\ufe0f  WARNING: Running in BYPASS mode. "
            "All security checks disabled. Do NOT use in production."
        )
        return None

    # 3. Assemble components
    if tool_registry is None:
        # Standalone fallback (e.g. tests without McpServer)
        from viyv_mcp.server.registry import McpRegistry

        tool_registry = McpRegistry()

    audit_logger = setup_audit_logger(config.audit_log_path)
    service = SecurityService(config, tool_registry, audit_logger)

    # 4. stdio JWT (process-scoped identity)
    stdio_jwt = os.environ.get("VIYV_MCP_JWT")
    if stdio_jwt:
        try:
            identity = service.authenticate_token(stdio_jwt)
            set_agent_identity(identity)
            service.stdio_identity = identity
            logger.info(
                f"Security: stdio identity established — "
                f"sub={identity.sub}, ns={identity.namespace}, "
                f"clearance={identity.clearance}"
            )
        except Exception as exc:
            logger.error(
                f"Security: failed to validate VIYV_MCP_JWT — "
                f"{type(exc).__name__}: {exc}"
            )
            if config.auth_mode == AuthMode.AUTHENTICATED:
                logger.critical(
                    "Security: cannot start in authenticated mode without a valid JWT"
                )
                raise SystemExit(1)

    logger.info(f"Security: layer created -- mode={config.auth_mode.value}")
    return SecurityLayer(service)
