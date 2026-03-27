"""McpServer — direct mcp SDK wrapper replacing FastMCP.

Owns a :class:`McpRegistry` for tools/resources/prompts, wires handler
decorators on the low-level ``mcp.server.lowlevel.Server``, integrates
security at the handler level, and provides both stdio and HTTP transports.
"""

from __future__ import annotations

import inspect
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable

from mcp.server.lowlevel import NotificationOptions, Server as LowLevelServer
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError
import mcp.types as types

from starlette.applications import Starlette
from starlette.routing import Mount

from viyv_mcp.server.registry import (
    McpRegistry,
    ToolEntry,
    ResourceEntry,
    PromptEntry,
)
from viyv_mcp.app.security.domain.models import ToolSecurityMeta

logger = logging.getLogger(__name__)


class McpServer:
    """MCP server using the ``mcp`` SDK directly (no FastMCP).

    Provides the same public API surface that viyv_mcp previously consumed
    from FastMCP: tool/resource/prompt registration, security integration,
    stdio and HTTP transports.
    """

    def __init__(
        self,
        name: str,
        *,
        version: str | None = None,
        lifespan: Callable | None = None,
    ) -> None:
        self.name = name
        self.registry = McpRegistry()
        self._security_service: Any = None

        if lifespan is None:
            @asynccontextmanager
            async def _noop_lifespan(server):
                yield {}
            lifespan = _noop_lifespan

        self._server = LowLevelServer(
            name=name,
            version=version,
            lifespan=lifespan,
        )
        self._register_handlers()

    @property
    def low_level_server(self) -> LowLevelServer:
        return self._server

    def set_security_service(self, service: Any) -> None:
        self._security_service = service

    # ------------------------------------------------------------------ #
    #  MCP protocol handlers                                              #
    # ------------------------------------------------------------------ #

    def _register_handlers(self) -> None:
        @self._server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            entries = self.registry.list_tools()
            tools = [e.to_mcp_tool() for e in entries]
            svc = self._security_service
            if svc and not svc.is_bypass:
                from viyv_mcp.app.security.context import get_agent_identity

                agent = get_agent_identity()
                if agent is None:
                    return []
                return svc.filter_tools_for_agent(agent, tools)
            return tools

        @self._server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict | None
        ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            svc = self._security_service
            if svc and not svc.is_bypass:
                from viyv_mcp.app.security.context import get_agent_identity

                agent = get_agent_identity()
                if agent is None:
                    raise McpError(
                        types.ErrorData(code=-32001, message="Authentication failed")
                    )
                result = svc.authorize_tool_call(agent, name)
                svc.log_access(agent, name, result)
                if not result.allowed:
                    if result.reason == "namespace":
                        raise McpError(
                            types.ErrorData(
                                code=-32601,
                                message=f"Tool '{name}' not found",
                            )
                        )
                    raise McpError(
                        types.ErrorData(
                            code=-32001,
                            message=f"Access denied: insufficient clearance for tool '{name}'",
                        )
                    )
            elif svc and svc.is_bypass:
                svc.log_bypass_access(name)

            entry = self.registry.get_tool(name)
            if entry is None:
                raise McpError(
                    types.ErrorData(code=-32601, message=f"Tool '{name}' not found")
                )
            try:
                raw = await entry.fn(**(arguments or {}))
            except McpError:
                raise
            except Exception as exc:
                logger.warning(f"Tool '{name}' raised: {type(exc).__name__}: {exc}")
                raise McpError(
                    types.ErrorData(code=-32000, message=str(exc))
                )
            return _normalize_tool_result(raw)

        @self._server.list_resources()
        async def handle_list_resources() -> list[types.Resource]:
            return [
                types.Resource(
                    uri=types.AnyUrl(e.uri),
                    name=e.name,
                    description=e.description,
                    mimeType=e.mime_type,
                )
                for e in self.registry.list_resources()
            ]

        @self._server.read_resource()
        async def handle_read_resource(uri: types.AnyUrl) -> str | bytes:
            uri_str = str(uri)
            entry = self.registry.get_resource(uri_str)
            if entry is None:
                raise McpError(
                    types.ErrorData(
                        code=-32601, message=f"Resource '{uri_str}' not found"
                    )
                )
            fn = entry.fn
            if inspect.iscoroutinefunction(fn):
                return await fn(uri=uri_str)
            return fn(uri=uri_str)

        @self._server.list_prompts()
        async def handle_list_prompts() -> list[types.Prompt]:
            return [
                types.Prompt(
                    name=e.name,
                    description=e.description,
                    arguments=e.arguments or None,
                )
                for e in self.registry.list_prompts()
            ]

        @self._server.get_prompt()
        async def handle_get_prompt(
            name: str, arguments: dict[str, str] | None
        ) -> types.GetPromptResult:
            entry = self.registry.get_prompt(name)
            if entry is None:
                raise McpError(
                    types.ErrorData(
                        code=-32601, message=f"Prompt '{name}' not found"
                    )
                )
            fn = entry.fn
            args = arguments or {}
            raw = await fn(**args) if inspect.iscoroutinefunction(fn) else fn(**args)
            if isinstance(raw, types.GetPromptResult):
                return raw
            if isinstance(raw, str):
                return types.GetPromptResult(
                    messages=[
                        types.PromptMessage(
                            role="user",
                            content=types.TextContent(type="text", text=raw),
                        )
                    ]
                )
            if isinstance(raw, list):
                return types.GetPromptResult(messages=raw)
            return types.GetPromptResult(messages=raw)

    # ------------------------------------------------------------------ #
    #  Registration helpers                                               #
    # ------------------------------------------------------------------ #

    def register_tool(
        self,
        name: str,
        description: str,
        fn: Callable,
        input_schema: dict,
        *,
        tags: set[str] | None = None,
        group: str | None = None,
        title: str | None = None,
        destructive: bool | None = None,
        namespace: str | None = None,
        security_level: int | None = None,
    ) -> None:
        entry = ToolEntry(
            name=name,
            description=description,
            fn=fn,
            input_schema=input_schema,
            tags=tags or set(),
            group=group,
            title=title,
            destructive=destructive,
            security=ToolSecurityMeta(
                namespace=namespace or "common",
                security_level=security_level,
            ),
        )
        self.registry.register_tool(entry)

    def remove_tool(self, name: str) -> None:
        self.registry.unregister_tool(name)

    # ------------------------------------------------------------------ #
    #  HTTP Transport                                                     #
    # ------------------------------------------------------------------ #

    def http_app(
        self,
        *,
        path: str = "/",
        stateless_http: bool | None = None,
    ) -> Starlette:
        """Create a Starlette ASGI app with StreamableHTTP transport."""
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        session_manager = StreamableHTTPSessionManager(
            app=self._server,
            stateless=bool(stateless_http),
        )

        async def handle_mcp(scope, receive, send):
            await session_manager.handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app):
            async with session_manager.run():
                logger.info(f"MCP HTTP transport ready (stateless={bool(stateless_http)})")
                yield

        return Starlette(
            routes=[Mount(path, app=handle_mcp)],
            lifespan=lifespan,
        )

    # ------------------------------------------------------------------ #
    #  stdio Transport                                                    #
    # ------------------------------------------------------------------ #

    async def run_stdio_async(self) -> None:
        """Run the server over stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            init_options = self._server.create_initialization_options(
                notification_options=NotificationOptions(tools_changed=True),
            )
            logger.info(f"Starting MCP server '{self.name}' with transport 'stdio'")
            await self._server.run(read_stream, write_stream, init_options)


def _normalize_tool_result(
    result: Any,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Convert tool return values to MCP content blocks."""
    # Already a list of content blocks (or empty list)
    if isinstance(result, list):
        if not result:
            return []
        if hasattr(result[0], "type"):
            return result
    # CallToolResult-like (from bridge sessions / WS bridge)
    if hasattr(result, "content") and isinstance(getattr(result, "content"), list):
        return result.content
    # Plain string
    if isinstance(result, str):
        return [types.TextContent(type="text", text=result)]
    # Dict
    if isinstance(result, dict):
        return [types.TextContent(type="text", text=json.dumps(result))]
    # None
    if result is None:
        return []
    # Fallback
    return [types.TextContent(type="text", text=str(result))]
