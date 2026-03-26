"""Security subsystem — Composition Root.

Call :func:`create_security_layer` from ``core.py`` to initialise the entire
security stack.  Returns ``None`` in bypass mode (zero overhead for existing
users).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from viyv_mcp.app.security.context import set_agent_identity
from viyv_mcp.app.security.domain.models import AuthMode
from viyv_mcp.app.security.infrastructure.audit_writer import setup_audit_logger
from viyv_mcp.app.security.infrastructure.config_loader import (
    SecurityConfig,
    load_security_config,
    validate_config,
)
from viyv_mcp.app.security.service import SecurityService
from viyv_mcp.app.security.tool_registry import ToolSecurityRegistry

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from starlette.types import ASGIApp

    from viyv_mcp.app.security.fastmcp_middleware import ViyvSecurityMiddleware

logger = logging.getLogger(__name__)


class SecurityLayer:
    """Façade returned by :func:`create_security_layer`.

    ``core.py`` only needs to call :pymethod:`register_middleware` and
    :pymethod:`wrap_asgi`.
    """

    def __init__(
        self,
        service: SecurityService,
        middleware: ViyvSecurityMiddleware,
    ) -> None:
        self.service = service
        self.middleware = middleware

    def wrap_asgi(self, app: ASGIApp) -> ASGIApp:
        """Wrap *app* with the JWT-extracting ASGI layer (HTTP only)."""
        from viyv_mcp.app.security.asgi_jwt_extractor import JWTExtractorMiddleware

        return JWTExtractorMiddleware(app, self.service)


def create_security_layer() -> SecurityLayer | None:
    """Bootstrap the entire security subsystem.

    Returns ``None`` when running in **bypass** mode so that ``core.py`` can
    skip all security-related wiring.
    """

    # 1. Load & validate config
    config = load_security_config()
    validate_config(config)

    # 2. Bypass → early exit
    if config.auth_mode == AuthMode.BYPASS:
        logger.warning(
            "\u26a0\ufe0f  WARNING: Running in BYPASS mode. "
            "All security checks disabled. Do NOT use in production."
        )
        return None

    # 3. Assemble components
    registry = ToolSecurityRegistry()
    audit_logger = setup_audit_logger(config.audit_log_path)
    service = SecurityService(config, registry, audit_logger)

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
            # Log the error type but not the full message (may contain token fragments)
            logger.error(
                f"Security: failed to validate VIYV_MCP_JWT — "
                f"{type(exc).__name__}: {exc}"
            )
            if config.auth_mode == AuthMode.AUTHENTICATED:
                logger.critical("Security: cannot start in authenticated mode without a valid JWT")
                raise SystemExit(1)

    # 5. Register observer hook for tool metadata
    _register_tool_event_hook(registry)

    # 6. Build FastMCP middleware
    from viyv_mcp.app.security.fastmcp_middleware import ViyvSecurityMiddleware

    middleware = ViyvSecurityMiddleware(service)

    logger.info(
        f"Security: layer created — mode={config.auth_mode.value}, "
        f"levels={list(config.security_levels.keys())}"
    )
    return SecurityLayer(service, middleware)


def _register_tool_event_hook(registry: ToolSecurityRegistry) -> None:
    """Wire the Observer hook so that tool registration / unregistration
    events automatically update the security registry.
    """
    from viyv_mcp.app.security.domain.models import ToolSecurityMeta

    try:
        from viyv_mcp.decorators import add_tool_event_hook
    except ImportError:
        logger.debug("Security: decorators.add_tool_event_hook not available — skipping hook")
        return

    def _on_tool_event(event: str, tool_name: str, metadata: dict[str, Any] | None) -> None:
        if event == "registered" and metadata:
            registry.register(
                tool_name,
                ToolSecurityMeta(
                    namespace=metadata.get("namespace") or "common",
                    security_level=metadata.get("security_level") or "public",
                ),
            )
        elif event == "unregistered":
            registry.unregister(tool_name)

    add_tool_event_hook(_on_tool_event)
