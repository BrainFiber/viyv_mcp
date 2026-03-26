"""Tests for domain policy — pure functions, no mocks needed."""

import pytest

from viyv_mcp.app.security.domain.models import AgentIdentity, DEFAULT_SECURITY_LEVELS
from viyv_mcp.app.security.domain.policy import (
    authorize_tool_access,
    check_clearance,
    check_namespace_visibility,
    compute_trusted_namespaces,
    resolve_security_level_rank,
)


# --- compute_trusted_namespaces ---

def test_trusted_ns_includes_own_and_common():
    agent = AgentIdentity(sub="a", clearance="public", namespace="hr")
    ns = compute_trusted_namespaces(agent)
    assert "hr" in ns
    assert "common" in ns


def test_trusted_ns_includes_trust():
    agent = AgentIdentity(sub="a", clearance="public", namespace="hr", trust=("fin",))
    ns = compute_trusted_namespaces(agent)
    assert "fin" in ns


def test_trusted_ns_no_implicit_common():
    agent = AgentIdentity(sub="a", clearance="public", namespace="hr")
    ns = compute_trusted_namespaces(agent, implicit_trust_common=False)
    assert "common" not in ns
    assert "hr" in ns


# --- check_namespace_visibility ---

def test_namespace_visible():
    assert check_namespace_visibility("hr", frozenset({"hr", "common"}))


def test_namespace_not_visible():
    assert not check_namespace_visibility("finance", frozenset({"hr", "common"}))


# --- check_clearance ---

def test_clearance_sufficient():
    assert check_clearance(2, 1)
    assert check_clearance(2, 2)


def test_clearance_insufficient():
    assert not check_clearance(1, 2)


# --- resolve_security_level_rank ---

def test_resolve_known_level():
    assert resolve_security_level_rank("internal", DEFAULT_SECURITY_LEVELS) == 1


def test_resolve_unknown_level():
    with pytest.raises(ValueError, match="Unknown security level"):
        resolve_security_level_rank("top_secret", DEFAULT_SECURITY_LEVELS)


# --- authorize_tool_access ---

def test_authorize_allowed():
    agent = AgentIdentity(sub="a", clearance="confidential", namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", "internal",
        trusted_namespaces=trusted,
        security_levels=DEFAULT_SECURITY_LEVELS,
    )
    assert result.allowed


def test_authorize_denied_namespace():
    agent = AgentIdentity(sub="a", clearance="confidential", namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "finance", "public",
        trusted_namespaces=trusted,
        security_levels=DEFAULT_SECURITY_LEVELS,
    )
    assert not result.allowed
    assert result.reason == "namespace"


def test_authorize_denied_clearance():
    agent = AgentIdentity(sub="a", clearance="public", namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", "confidential",
        trusted_namespaces=trusted,
        security_levels=DEFAULT_SECURITY_LEVELS,
    )
    assert not result.allowed
    assert result.reason == "clearance"


def test_authorize_unknown_agent_clearance():
    agent = AgentIdentity(sub="a", clearance="unknown_level", namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", "public",
        trusted_namespaces=trusted,
        security_levels=DEFAULT_SECURITY_LEVELS,
    )
    assert not result.allowed
    assert result.reason == "clearance"
    assert "unknown_level" in result.detail


def test_authorize_unknown_tool_level():
    agent = AgentIdentity(sub="a", clearance="public", namespace="hr")
    trusted = frozenset({"hr", "common"})
    result = authorize_tool_access(
        agent, "hr", "unknown_level",
        trusted_namespaces=trusted,
        security_levels=DEFAULT_SECURITY_LEVELS,
    )
    assert not result.allowed
    assert result.reason == "clearance"
    assert "unknown_level" in result.detail
