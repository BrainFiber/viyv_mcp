"""Tests for domain policy — pure functions, no mocks needed."""

from viyv_mcp.app.security.domain.models import AgentIdentity
from viyv_mcp.app.security.domain.policy import (
    authorize_tool_access,
    check_clearance,
    check_namespace_visibility,
    compute_trusted_namespaces,
)


# --- compute_trusted_namespaces ---

def test_trusted_ns_includes_own_and_common():
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")
    ns = compute_trusted_namespaces(agent)
    assert "hr" in ns
    assert "common" in ns


def test_trusted_ns_includes_trust():
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr", trust=("fin",))
    ns = compute_trusted_namespaces(agent)
    assert "fin" in ns


def test_trusted_ns_no_implicit_common():
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")
    ns = compute_trusted_namespaces(agent, implicit_trust_common=False)
    assert "common" not in ns
    assert "hr" in ns


# --- check_namespace_visibility ---

def test_namespace_visible():
    assert check_namespace_visibility("hr", frozenset({"hr", "common"}))


def test_namespace_not_visible():
    assert not check_namespace_visibility("finance", frozenset({"hr", "common"}))


# --- check_clearance (numeric: lower = higher privilege) ---

def test_clearance_sufficient():
    assert check_clearance(1, 2)       # agent=1 <= tool=2 -> allowed
    assert check_clearance(2, 2)       # exact match


def test_clearance_insufficient():
    assert not check_clearance(2, 1)   # agent=2 > tool=1 -> denied


def test_clearance_both_none():
    assert check_clearance(None, None)  # no restriction


def test_clearance_agent_none_tool_set():
    assert not check_clearance(None, 2)  # no privilege, tool restricted


def test_clearance_agent_set_tool_none():
    assert check_clearance(2, None)      # tool unrestricted


# --- authorize_tool_access ---

def test_authorize_allowed():
    agent = AgentIdentity(sub="a", clearance=1, namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", 2,
        trusted_namespaces=trusted,
    )
    assert result.allowed


def test_authorize_denied_namespace():
    agent = AgentIdentity(sub="a", clearance=1, namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "finance", None,
        trusted_namespaces=trusted,
    )
    assert not result.allowed
    assert result.reason == "namespace"


def test_authorize_denied_clearance():
    agent = AgentIdentity(sub="a", clearance=3, namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", 0,
        trusted_namespaces=trusted,
    )
    assert not result.allowed
    assert result.reason == "clearance"


def test_authorize_tool_unrestricted():
    agent = AgentIdentity(sub="a", clearance=3, namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", None,
        trusted_namespaces=trusted,
    )
    assert result.allowed


def test_authorize_agent_no_clearance():
    agent = AgentIdentity(sub="a", clearance=None, namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", 1,
        trusted_namespaces=trusted,
    )
    assert not result.allowed
    assert result.reason == "clearance"
