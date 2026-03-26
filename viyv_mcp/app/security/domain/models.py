"""Domain models for the security subsystem.

No external dependencies — only Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class AuthMode(Enum):
    """Operating mode for the security subsystem."""

    BYPASS = "bypass"
    AUTHENTICATED = "authenticated"
    DENY_ALL = "deny_all"


@dataclass(frozen=True)
class SecurityLevel:
    """A named security clearance level with a numeric rank."""

    name: str
    rank: int


@dataclass(frozen=True)
class AgentIdentity:
    """Identity extracted from a validated JWT.

    ``trusted_namespaces`` is **not** computed here because the calculation
    depends on configuration (``implicit_trust_common``).  Use
    :func:`~viyv_mcp.app.security.domain.policy.compute_trusted_namespaces`
    instead.
    """

    sub: str
    clearance: str
    namespace: str
    trust: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSecurityMeta:
    """Security metadata attached to a single tool."""

    namespace: str = "common"
    security_level: str = "public"


@dataclass(frozen=True)
class AuthResult:
    """Outcome of an authorization check."""

    allowed: bool
    reason: str  # "" | "namespace" | "clearance"
    detail: str = ""


# Default security levels (used when security.yaml is absent).
DEFAULT_SECURITY_LEVELS: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}
