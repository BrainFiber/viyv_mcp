"""FastMCP native middleware — runs for **both** stdio and HTTP transports.

Uses :func:`get_agent_identity` to read the agent identity from a
:class:`~contextvars.ContextVar` set by:

* **HTTP** — :class:`~viyv_mcp.app.security.asgi_jwt_extractor.JWTExtractorMiddleware`
* **stdio** — once at startup in :func:`~viyv_mcp.app.security.create_security_layer`
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from mcp.shared.exceptions import McpError

import mcp.types as mt

from viyv_mcp.app.security.context import get_agent_identity
from viyv_mcp.app.security.domain.models import AuthMode

if TYPE_CHECKING:
    from fastmcp.tools.tool import Tool, ToolResult
    from viyv_mcp.app.security.service import SecurityService

logger = logging.getLogger(__name__)


class ViyvSecurityMiddleware(Middleware):
    """Enforce namespace visibility and clearance checks on every tool
    operation, regardless of the transport layer.
    """

    def __init__(self, service: SecurityService) -> None:
        self._service = service

    # ------------------------------------------------------------------ #
    #  tools/call                                                         #
    # ------------------------------------------------------------------ #
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        tool_name: str = context.message.name

        # --- bypass --------------------------------------------------- #
        if self._service.is_bypass:
            self._service.log_bypass_access(tool_name)
            return await call_next(context)

        # --- authenticate --------------------------------------------- #
        agent = get_agent_identity()

        if agent is None:
            mode = self._service.auth_mode.value
            logger.warning(
                f"Security: no identity for tools/call '{tool_name}' (mode={mode})"
            )
            raise McpError(
                mt.ErrorData(code=-32001, message="Authentication failed")
            )

        # --- authorize ------------------------------------------------ #
        result = self._service.authorize_tool_call(agent, tool_name)
        self._service.log_access(agent, tool_name, result)

        if not result.allowed:
            if result.reason == "namespace":
                # Hide tool existence
                raise McpError(
                    mt.ErrorData(
                        code=-32601,
                        message=f"Tool '{tool_name}' not found",
                    )
                )
            # clearance
            raise McpError(
                mt.ErrorData(
                    code=-32001,
                    message=f"Access denied: insufficient clearance for tool '{tool_name}'",
                )
            )

        return await call_next(context)

    # ------------------------------------------------------------------ #
    #  tools/list                                                         #
    # ------------------------------------------------------------------ #
    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Any]],
    ) -> Sequence[Any]:
        tools = await call_next(context)

        if self._service.is_bypass:
            return tools

        agent = get_agent_identity()

        if agent is None:
            # No identity: hide all tools regardless of mode
            return []

        return self._service.filter_tools_for_agent(agent, tools)
