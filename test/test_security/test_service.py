"""Tests for SecurityService."""

import logging
import logging.handlers

from viyv_mcp.app.security.domain.models import AgentIdentity, AuthMode, AuthResult, ToolSecurityMeta
from viyv_mcp.app.security.infrastructure.config_loader import SecurityConfig
from viyv_mcp.app.security.service import SecurityService
from viyv_mcp.server.registry import McpRegistry, ToolEntry

SECRET = "a-test-secret-that-is-at-least-32-bytes-long!"


def _noop_fn(**kw):
    pass


def _make_service(auth_mode=AuthMode.AUTHENTICATED) -> SecurityService:
    config = SecurityConfig(auth_mode=auth_mode, jwt_secret=SECRET)
    registry = McpRegistry()
    audit = logging.getLogger("test.audit")
    return SecurityService(config, registry, audit)


def test_authorize_allowed():
    svc = _make_service()
    svc._tool_registry.register_tool(ToolEntry(name="add", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="common", security_level=None)))
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")
    result = svc.authorize_tool_call(agent, "add")
    assert result.allowed


def test_authorize_denied_namespace():
    svc = _make_service()
    svc._tool_registry.register_tool(ToolEntry(name="secret", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="finance", security_level=None)))
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")
    result = svc.authorize_tool_call(agent, "secret")
    assert not result.allowed
    assert result.reason == "namespace"


def test_authorize_denied_clearance():
    svc = _make_service()
    svc._tool_registry.register_tool(ToolEntry(name="classify", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="hr", security_level=0)))
    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")
    result = svc.authorize_tool_call(agent, "classify")
    assert not result.allowed
    assert result.reason == "clearance"


def test_filter_tools():
    svc = _make_service()
    svc._tool_registry.register_tool(ToolEntry(name="t1", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="hr", security_level=None)))
    svc._tool_registry.register_tool(ToolEntry(name="t2", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="finance", security_level=None)))
    svc._tool_registry.register_tool(ToolEntry(name="t3", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta(namespace="common", security_level=None)))

    agent = AgentIdentity(sub="a", clearance=2, namespace="hr")

    class FakeTool:
        def __init__(self, name):
            self.name = name

    tools = [FakeTool("t1"), FakeTool("t2"), FakeTool("t3")]
    filtered = svc.filter_tools_for_agent(agent, tools)
    names = [t.name for t in filtered]
    assert "t1" in names  # hr = own namespace
    assert "t3" in names  # common = implicit trust
    assert "t2" not in names  # finance = not trusted


def test_authenticate_token():
    import time
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt

    svc = _make_service()
    payload = {
        "sub": "agent-1", "clearance": 1, "namespace": "hr",
        "trust": ["common"], "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    token = encode_jwt(payload, SECRET)
    identity = svc.authenticate_token(token)
    assert identity.sub == "agent-1"
    assert identity.clearance == 1
    assert identity.namespace == "hr"
    assert identity.trust == ("common",)


def test_authenticate_token_missing_claim():
    import time
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt, JWTDecodeError
    import pytest

    svc = _make_service()
    payload = {"sub": "agent-1", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    token = encode_jwt(payload, SECRET)
    with pytest.raises(JWTDecodeError, match="Missing required JWT claim"):
        svc.authenticate_token(token)


def test_authenticate_token_no_clearance():
    """JWT without clearance claim -> identity.clearance is None."""
    import time
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt

    svc = _make_service()
    payload = {
        "sub": "agent-1", "namespace": "hr",
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    token = encode_jwt(payload, SECRET)
    identity = svc.authenticate_token(token)
    assert identity.clearance is None


def test_authenticate_token_string_clearance():
    """Legacy string clearance -> treated as None with warning."""
    import time
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt

    svc = _make_service()
    payload = {
        "sub": "agent-1", "clearance": "internal", "namespace": "hr",
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    token = encode_jwt(payload, SECRET)
    identity = svc.authenticate_token(token)
    assert identity.clearance is None


def test_authenticate_token_coerces_trust():
    import time
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt

    svc = _make_service()
    payload = {
        "sub": "agent-1", "clearance": 0, "namespace": "hr",
        "trust": [123, "common"],  # non-string in trust
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    token = encode_jwt(payload, SECRET)
    identity = svc.authenticate_token(token)
    assert identity.trust == ("123", "common")


def test_log_access_allowed():
    import json

    svc = _make_service()
    svc._tool_registry.register_tool(ToolEntry(name="tool1", description="", fn=_noop_fn, input_schema={"type":"object","properties":{}}, security=ToolSecurityMeta()))
    agent = AgentIdentity(sub="user1", clearance=3, namespace="hr")
    result = AuthResult(allowed=True, reason="")

    # Use a handler that captures log output
    handler = logging.handlers.MemoryHandler(capacity=100)
    svc._audit_logger.addHandler(handler)
    svc._audit_logger.setLevel(logging.INFO)

    svc.log_access(agent, "tool1", result)

    handler.flush()
    assert len(handler.buffer) == 1
    record = json.loads(handler.buffer[0].getMessage())
    assert record["result"] == "allowed"
    assert record["agent"] == "user1"
    svc._audit_logger.removeHandler(handler)


def test_log_bypass_access():
    import json

    svc = _make_service(auth_mode=AuthMode.BYPASS)
    handler = logging.handlers.MemoryHandler(capacity=100)
    svc._audit_logger.addHandler(handler)
    svc._audit_logger.setLevel(logging.INFO)

    svc.log_bypass_access("tool1")

    handler.flush()
    assert len(handler.buffer) == 1
    record = json.loads(handler.buffer[0].getMessage())
    assert record["mode"] == "bypass"
    svc._audit_logger.removeHandler(handler)


def test_filter_tools_skips_nameless_objects():
    svc = _make_service()

    class NoName:
        pass

    filtered = svc.filter_tools_for_agent(
        AgentIdentity(sub="a", clearance=3, namespace="hr"),
        [NoName()],
    )
    assert filtered == []
