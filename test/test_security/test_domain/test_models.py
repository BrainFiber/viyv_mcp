"""Tests for domain models."""

from viyv_mcp.app.security.domain.models import (
    AgentIdentity,
    AuthMode,
    AuthResult,
    DEFAULT_SECURITY_LEVELS,
    SecurityLevel,
    ToolSecurityMeta,
)


def test_agent_identity_frozen():
    agent = AgentIdentity(sub="a", clearance="public", namespace="ns")
    assert agent.sub == "a"
    assert agent.trust == ()


def test_agent_identity_with_trust():
    agent = AgentIdentity(sub="a", clearance="public", namespace="ns", trust=("x", "y"))
    assert agent.trust == ("x", "y")


def test_tool_security_meta_defaults():
    meta = ToolSecurityMeta()
    assert meta.namespace == "common"
    assert meta.security_level == "public"


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


def test_default_security_levels():
    assert DEFAULT_SECURITY_LEVELS["public"] == 0
    assert DEFAULT_SECURITY_LEVELS["restricted"] == 3


def test_security_level():
    sl = SecurityLevel(name="top_secret", rank=99)
    assert sl.name == "top_secret"
    assert sl.rank == 99
