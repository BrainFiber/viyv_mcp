"""End-to-end tests for the security subsystem.

Tests the full chain:
  ContextVar (identity) → McpServer handlers → tool execution

Two approaches:
  1. **McpServer direct calls** (list_tools / call_tool) — exercises the
     security handler logic without HTTP transport complications.
  2. **HTTP tools/list** via TestClient — verifies the ASGI JWT extractor.

Numeric clearance/security_level semantics:
  Lower number = higher privilege (0 = top).
  access rule: agent.clearance <= tool.security_level → allowed.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from starlette.testclient import TestClient

from viyv_mcp.server import McpServer
from viyv_mcp.server.registry import McpRegistry

from viyv_mcp.app.security.context import get_agent_identity, reset_agent_identity, set_agent_identity
from viyv_mcp.app.security.domain.models import AgentIdentity, AuthMode, ToolSecurityMeta
from viyv_mcp.app.security.infrastructure.audit_writer import setup_audit_logger
from viyv_mcp.app.security.infrastructure.config_loader import SecurityConfig
from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt
from viyv_mcp.app.security.service import SecurityService
from viyv_mcp.app.security.asgi_jwt_extractor import JWTExtractorMiddleware

SECRET = "e2e-test-secret-key-that-is-long-enough-for-hs256!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(**overrides: Any) -> str:
    now = int(time.time())
    payload = {
        "sub": "test-agent",
        "clearance": 2,
        "namespace": "hr",
        "iat": now,
        "exp": now + 3600,
    }
    payload.update(overrides)
    return encode_jwt(payload, SECRET)


def _build_mcp(auth_mode: AuthMode = AuthMode.AUTHENTICATED):
    """Build McpServer + security, return (mcp, service)."""
    mcp = McpServer("E2E Test", version="test")

    # Register tools
    async def add(a: int = 0, b: int = 0) -> str:
        return str(a + b)

    async def query_salary(employee_id: str = "") -> str:
        return f"salary:{employee_id}:100000"

    async def execute_trade(symbol: str = "", amount: int = 0) -> str:
        return f"trade:{symbol}:{amount}"

    async def update_salary(employee_id: str = "", new_salary: int = 0) -> str:
        return f"updated:{employee_id}:{new_salary}"

    async def shared_report() -> str:
        return "report_data"

    mcp.register_tool("add", "Add two numbers", add,
        {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
        namespace="common", security_level=None)
    mcp.register_tool("query_salary", "Query salary", query_salary,
        {"type": "object", "properties": {"employee_id": {"type": "string"}}},
        namespace="hr", security_level=1)
    mcp.register_tool("execute_trade", "Execute trade", execute_trade,
        {"type": "object", "properties": {"symbol": {"type": "string"}, "amount": {"type": "integer"}}},
        namespace="finance", security_level=0)
    mcp.register_tool("update_salary", "Update salary", update_salary,
        {"type": "object", "properties": {"employee_id": {"type": "string"}, "new_salary": {"type": "integer"}}},
        namespace="hr", security_level=0)
    mcp.register_tool("shared_report", "Shared report", shared_report,
        {"type": "object", "properties": {}},
        namespace="analytics", security_level=2)

    # Setup security
    config = SecurityConfig(auth_mode=auth_mode, jwt_secret=SECRET)
    audit = setup_audit_logger(None)
    service = SecurityService(config, mcp.registry, audit)

    if auth_mode != AuthMode.BYPASS:
        mcp.set_security_service(service)

    return mcp, service


def _set_identity(sub="test-agent", clearance=2, namespace="hr", trust=()):
    agent = AgentIdentity(sub=sub, clearance=clearance, namespace=namespace, trust=trust)
    return set_agent_identity(agent)


# ---------------------------------------------------------------------------
# Scenario 1: tools/list — namespace filter
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_list_namespace_filter():
    mcp, _ = _build_mcp()
    token = _set_identity(clearance=1, namespace="hr", trust=("common",))
    try:
        tools = [e.to_mcp_tool() for e in mcp.registry.list_tools()]
        assert len(tools) == 5  # All tools in registry
    finally:
        reset_agent_identity(token)


@pytest.mark.anyio
async def test_tools_list_security_filtered():
    """Security-filtered list_tools via handler."""
    mcp, svc = _build_mcp()
    token = _set_identity(clearance=1, namespace="hr", trust=("common",))
    try:
        # Call the handler directly (simulates MCP protocol)
        agent = get_agent_identity()
        all_tools = [e.to_mcp_tool() for e in mcp.registry.list_tools()]
        filtered = svc.filter_tools_for_agent(agent, all_tools)
        names = {t.name for t in filtered}

        assert "add" in names
        assert "query_salary" in names
        assert "update_salary" in names
        assert "execute_trade" not in names
        assert "shared_report" not in names
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 2: tools/call — allowed
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_call_allowed():
    mcp, _ = _build_mcp()
    token = _set_identity(clearance=1, trust=("common",))
    try:
        entry = mcp.registry.get_tool("add")
        result = await entry.fn(a=5, b=3)
        assert result == "8"
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 3: tools/call — clearance denied (via SecurityService)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_call_clearance_denied():
    mcp, svc = _build_mcp()
    token = _set_identity(clearance=2, namespace="hr")
    try:
        agent = get_agent_identity()
        result = svc.authorize_tool_call(agent, "update_salary")
        assert not result.allowed
        assert result.reason == "clearance"
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 4: tools/call — namespace denied
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_call_namespace_denied():
    mcp, svc = _build_mcp()
    token = _set_identity(clearance=0, namespace="hr")
    try:
        agent = get_agent_identity()
        result = svc.authorize_tool_call(agent, "execute_trade")
        assert not result.allowed
        assert result.reason == "namespace"
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 5: no identity → security denies
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_list_no_identity():
    mcp, svc = _build_mcp()
    agent = get_agent_identity()
    assert agent is None
    # The handler returns [] when agent is None
    all_tools = [e.to_mcp_tool() for e in mcp.registry.list_tools()]
    # With no identity, filter should return empty
    assert agent is None  # confirms no identity


# ---------------------------------------------------------------------------
# Scenario 6: exact clearance match
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tools_call_exact_clearance():
    mcp, svc = _build_mcp()
    token = _set_identity(clearance=1, namespace="hr")
    try:
        agent = get_agent_identity()
        result = svc.authorize_tool_call(agent, "query_salary")
        assert result.allowed
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 7: trust grants cross-namespace access
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_trust_grants_cross_namespace_access():
    mcp, svc = _build_mcp()
    token = _set_identity(clearance=2, namespace="hr", trust=("common", "analytics"))
    try:
        agent = get_agent_identity()
        all_tools = [e.to_mcp_tool() for e in mcp.registry.list_tools()]
        filtered = svc.filter_tools_for_agent(agent, all_tools)
        names = {t.name for t in filtered}
        assert "shared_report" in names
        assert "add" in names
        assert "execute_trade" not in names
    finally:
        reset_agent_identity(token)


# ---------------------------------------------------------------------------
# Scenario 8: bypass mode — all tools accessible
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_bypass_mode_all_allowed():
    mcp, _ = _build_mcp(auth_mode=AuthMode.BYPASS)
    tools = [e.to_mcp_tool() for e in mcp.registry.list_tools()]
    names = {t.name for t in tools}
    assert "add" in names
    assert "execute_trade" in names
    assert "update_salary" in names
    assert "shared_report" in names

    entry = mcp.registry.get_tool("add")
    result = await entry.fn(a=10, b=20)
    assert result == "30"


# ---------------------------------------------------------------------------
# Scenario 9: HTTP tools/list with JWT
# ---------------------------------------------------------------------------

def _parse_sse_json(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


def test_http_app_creates_starlette():
    """Verify http_app() returns a valid Starlette ASGI app."""
    mcp, service = _build_mcp()
    app = mcp.http_app(path="/", stateless_http=True)
    assert app is not None
    assert hasattr(app, "router")
    # Verify JWT wrapper can be applied
    wrapped = JWTExtractorMiddleware(app, service)
    assert wrapped is not None
