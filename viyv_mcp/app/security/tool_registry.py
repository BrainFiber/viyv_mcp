"""Thread-safe registry mapping tool names to security metadata."""

from __future__ import annotations

import threading
from typing import Dict

from viyv_mcp.app.security.domain.models import ToolSecurityMeta

_DEFAULT_META = ToolSecurityMeta()  # common / public


class ToolSecurityRegistry:
    """Central store for tool security metadata.

    Populated via Observer hooks fired by :mod:`viyv_mcp.decorators` and
    :mod:`viyv_mcp.app.bridge_manager`.  Queried by
    :class:`~viyv_mcp.app.security.service.SecurityService` at authorization
    time.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, ToolSecurityMeta] = {}
        self._lock = threading.Lock()

    # -- mutators --------------------------------------------------------

    def register(self, tool_name: str, meta: ToolSecurityMeta) -> None:
        with self._lock:
            self._registry[tool_name] = meta

    def unregister(self, tool_name: str) -> None:
        with self._lock:
            self._registry.pop(tool_name, None)

    # -- queries ---------------------------------------------------------

    def get(self, tool_name: str) -> ToolSecurityMeta:
        """Return metadata for *tool_name*, or ``common/public`` default."""
        with self._lock:
            return self._registry.get(tool_name, _DEFAULT_META)

    def get_all(self) -> Dict[str, ToolSecurityMeta]:
        with self._lock:
            return dict(self._registry)
