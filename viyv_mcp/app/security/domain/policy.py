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
    agent_clearance: int | None,
    tool_security_level: int | None,
) -> bool:
    """Return ``True`` if the agent has sufficient clearance.

    - ``tool_security_level is None`` → unrestricted (always ``True``).
    - ``agent_clearance is None`` → no privilege (``False`` if tool is restricted).
    - Otherwise: ``agent_clearance <= tool_security_level`` (lower = higher privilege).
    """
    if tool_security_level is None:
        return True
    if agent_clearance is None:
        return False
    return agent_clearance <= tool_security_level


def authorize_tool_access(
    agent: AgentIdentity,
    tool_namespace: str,
    tool_security_level: int | None,
    *,
    trusted_namespaces: frozenset[str],
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
    if not check_clearance(agent.clearance, tool_security_level):
        return AuthResult(
            allowed=False,
            reason="clearance",
            detail=(
                f"Agent clearance {agent.clearance} insufficient "
                f"for tool level {tool_security_level}"
            ),
        )

    return AuthResult(allowed=True, reason="")
