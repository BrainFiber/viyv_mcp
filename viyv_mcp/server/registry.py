"""Thread-safe registries for tools, resources, and prompts.

Replaces both FastMCP's internal registries and the separate
ToolSecurityRegistry.  Security metadata is stored alongside each
tool in :class:`ToolEntry`, eliminating the Observer pattern.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

import mcp.types as types

from viyv_mcp.app.security.domain.models import ToolSecurityMeta

_DEFAULT_SECURITY = ToolSecurityMeta()


@dataclass
class ToolEntry:
    """A registered tool with its handler, MCP schema, and security metadata."""

    name: str
    description: str
    fn: Callable[..., Any]
    input_schema: dict
    tags: set[str] = field(default_factory=set)
    group: str | None = None
    title: str | None = None
    destructive: bool | None = None
    security: ToolSecurityMeta = field(default_factory=ToolSecurityMeta)

    def to_mcp_tool(self) -> types.Tool:
        annotations = None
        if self.title or self.destructive is not None:
            annotations = types.ToolAnnotations(
                title=self.title,
                destructiveHint=self.destructive,
            )
        return types.Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
            annotations=annotations,
        )


@dataclass
class ResourceEntry:
    """A registered resource."""

    uri: str
    name: str
    description: str
    fn: Callable[..., Any]
    mime_type: str | None = None


@dataclass
class PromptEntry:
    """A registered prompt."""

    name: str
    description: str
    fn: Callable[..., Any]
    arguments: list[types.PromptArgument] = field(default_factory=list)


class McpRegistry:
    """Thread-safe registry for tools, resources, and prompts.

    Also serves as the :class:`ToolMetadataProvider` consumed by
    :class:`~viyv_mcp.app.security.service.SecurityService` — the
    :meth:`get` method returns :class:`ToolSecurityMeta` for a tool.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolEntry] = {}
        self._resources: Dict[str, ResourceEntry] = {}
        self._prompts: Dict[str, PromptEntry] = {}
        self._lock = threading.Lock()

    # -- Tools ---------------------------------------------------------- #

    def register_tool(self, entry: ToolEntry) -> None:
        with self._lock:
            self._tools[entry.name] = entry

    def unregister_tool(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)

    def get_tool(self, name: str) -> ToolEntry | None:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> list[ToolEntry]:
        with self._lock:
            return list(self._tools.values())

    # -- ToolMetadataProvider (SecurityService 互換) ---------------------- #

    def get(self, tool_name: str) -> ToolSecurityMeta:
        """Return security metadata for *tool_name*, or default."""
        with self._lock:
            entry = self._tools.get(tool_name)
            return entry.security if entry else _DEFAULT_SECURITY

    def get_all(self) -> Dict[str, ToolSecurityMeta]:
        with self._lock:
            return {name: e.security for name, e in self._tools.items()}

    # -- Resources ------------------------------------------------------ #

    def register_resource(self, entry: ResourceEntry) -> None:
        with self._lock:
            self._resources[entry.uri] = entry

    def get_resource(self, uri: str) -> ResourceEntry | None:
        with self._lock:
            return self._resources.get(uri)

    def list_resources(self) -> list[ResourceEntry]:
        with self._lock:
            return list(self._resources.values())

    # -- Prompts -------------------------------------------------------- #

    def register_prompt(self, entry: PromptEntry) -> None:
        with self._lock:
            self._prompts[entry.name] = entry

    def get_prompt(self, name: str) -> PromptEntry | None:
        with self._lock:
            return self._prompts.get(name)

    def list_prompts(self) -> list[PromptEntry]:
        with self._lock:
            return list(self._prompts.values())
