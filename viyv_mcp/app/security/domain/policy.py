"""Pure authorization functions — no external dependencies, no side effects.

Every function takes only primitives or domain models and returns a
deterministic result.  This makes the policy layer trivially testable
without mocks.
"""

from __future__ import annotations

from viyv_mcp.app.security.domain.models import AgentIdentity, AuthResult


def compute_trusted_namespaces(
    agent: AgentIdentity,
    *,
    implicit_trust_common: bool = True,
) -> frozenset[str]:
    """Return the set of namespaces the *agent* is allowed to see.

    Always includes the agent's own namespace and those listed in ``trust``.
    When *implicit_trust_common* is ``True`` (the default), ``"common"`` is
    added automatically.
    """
    ns = {agent.namespace, *agent.trust}
    if implicit_trust_common:
        ns.add("common")
    return frozenset(ns)


def check_namespace_visibility(
    tool_ns: str,
    trusted_namespaces: frozenset[str],
) -> bool:
    """Return ``True`` if *tool_ns* is visible to the agent."""
    return tool_ns in trusted_namespaces


def check_clearance(
    agent_clearance_rank: int,
    tool_level_rank: int,
) -> bool:
    """Return ``True`` if the agent has sufficient clearance."""
    return agent_clearance_rank >= tool_level_rank


def resolve_security_level_rank(
    level_name: str,
    levels: dict[str, int],
) -> int:
    """Map a level name to its numeric rank.

    Raises :class:`ValueError` if *level_name* is not found in *levels*.
    """
    try:
        return levels[level_name]
    except KeyError:
        raise ValueError(
            f"Unknown security level {level_name!r}. "
            f"Known levels: {', '.join(sorted(levels))}"
        ) from None


def authorize_tool_access(
    agent: AgentIdentity,
    tool_namespace: str,
    tool_security_level: str,
    *,
    trusted_namespaces: frozenset[str],
    security_levels: dict[str, int],
) -> AuthResult:
    """Run both namespace and clearance checks, returning a single result."""

    # 1. Namespace visibility
    if not check_namespace_visibility(tool_namespace, trusted_namespaces):
        return AuthResult(
            allowed=False,
            reason="namespace",
            detail=f"Namespace '{tool_namespace}' not in agent's trusted namespaces",
        )

    # 2. Clearance
    try:
        agent_rank = resolve_security_level_rank(agent.clearance, security_levels)
    except ValueError:
        return AuthResult(
            allowed=False,
            reason="clearance",
            detail=f"Agent clearance '{agent.clearance}' is not a known security level",
        )

    try:
        tool_rank = resolve_security_level_rank(tool_security_level, security_levels)
    except ValueError:
        return AuthResult(
            allowed=False,
            reason="clearance",
            detail=f"Tool security level '{tool_security_level}' is not a known security level",
        )

    if not check_clearance(agent_rank, tool_rank):
        return AuthResult(
            allowed=False,
            reason="clearance",
            detail=(
                f"Agent clearance '{agent.clearance}' (rank {agent_rank}) "
                f"is below required '{tool_security_level}' (rank {tool_rank})"
            ),
        )

    return AuthResult(allowed=True, reason="")
