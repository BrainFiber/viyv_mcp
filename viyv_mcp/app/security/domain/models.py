"""Domain models for the security subsystem.

No external dependencies — only Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class AuthMode(Enum):
    """Operating mode for the security subsystem."""

    BYPASS = "bypass"
    AUTHENTICATED = "authenticated"
    DENY_ALL = "deny_all"


@dataclass(frozen=True)
class AgentIdentity:
    """Identity extracted from a validated JWT.

    ``clearance`` is a numeric value where lower numbers indicate higher
    privilege (0 = top).  ``None`` means no clearance was provided, which
    is treated as the lowest privilege level.

    ``trusted_namespaces`` is **not** computed here because the calculation
    depends on configuration (``implicit_trust_common``).  Use
    :func:`~viyv_mcp.app.security.domain.policy.compute_trusted_namespaces`
    instead.
    """

    sub: str
    clearance: int | None
    namespace: str
    trust: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSecurityMeta:
    """Security metadata attached to a single tool.

    ``security_level`` is a numeric value where lower numbers indicate
    higher restriction.  ``None`` means unrestricted (anyone can access).
    """

    namespace: str = "common"
    security_level: int | None = None


@dataclass(frozen=True)
class AuthResult:
    """Outcome of an authorization check."""

    allowed: bool
    reason: str  # "" | "namespace" | "clearance"
    detail: str = ""
