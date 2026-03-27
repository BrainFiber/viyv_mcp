"""Tests for domain models."""

from viyv_mcp.app.security.domain.models import (
    AgentIdentity,
    AuthMode,
    AuthResult,
    ToolSecurityMeta,
)


def test_agent_identity_frozen():
    agent = AgentIdentity(sub="a", clearance=0, namespace="ns")
    assert agent.sub == "a"
    assert agent.clearance == 0
    assert agent.trust == ()


def test_agent_identity_with_trust():
    agent = AgentIdentity(sub="a", clearance=1, namespace="ns", trust=("x", "y"))
    assert agent.trust == ("x", "y")


def test_agent_identity_clearance_none():
    agent = AgentIdentity(sub="a", clearance=None, namespace="ns")
    assert agent.clearance is None


def test_tool_security_meta_defaults():
    meta = ToolSecurityMeta()
    assert meta.namespace == "common"
    assert meta.security_level is None


def test_tool_security_meta_with_level():
    meta = ToolSecurityMeta(namespace="hr", security_level=1)
    assert meta.security_level == 1


def test_auth_result():
    ok = AuthResult(allowed=True, reason="")
    assert ok.allowed
    denied = AuthResult(allowed=False, reason="namespace", detail="not visible")
    assert not denied.allowed
    assert denied.reason == "namespace"


def test_auth_mode():
    assert AuthMode.BYPASS.value == "bypass"
    assert AuthMode.AUTHENTICATED.value == "authenticated"
    assert AuthMode.DENY_ALL.value == "deny_all"
