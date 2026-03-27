"""Tests for McpRegistry (security metadata queries)."""

from viyv_mcp.app.security.domain.models import ToolSecurityMeta
from viyv_mcp.server.registry import McpRegistry, ToolEntry


def _make_entry(name, namespace="common", security_level=None):
    async def _noop(**kw):
        pass
    return ToolEntry(
        name=name, description="", fn=_noop,
        input_schema={"type": "object", "properties": {}},
        security=ToolSecurityMeta(namespace=namespace, security_level=security_level),
    )


def test_register_and_get():
    reg = McpRegistry()
    reg.register_tool(_make_entry("query_salary", namespace="hr", security_level=1))
    meta = reg.get("query_salary")
    assert meta.namespace == "hr"
    assert meta.security_level == 1


def test_get_default():
    reg = McpRegistry()
    meta = reg.get("nonexistent")
    assert meta.namespace == "common"
    assert meta.security_level is None


def test_unregister():
    reg = McpRegistry()
    reg.register_tool(_make_entry("tool1", namespace="hr"))
    reg.unregister_tool("tool1")
    assert reg.get("tool1").namespace == "common"


def test_get_all():
    reg = McpRegistry()
    reg.register_tool(_make_entry("a", namespace="x"))
    reg.register_tool(_make_entry("b", namespace="y"))
    all_meta = reg.get_all()
    assert len(all_meta) == 2
    assert "a" in all_meta
    assert "b" in all_meta


def test_overwrite():
    reg = McpRegistry()
    reg.register_tool(_make_entry("t", namespace="old"))
    reg.register_tool(_make_entry("t", namespace="new"))
    assert reg.get("t").namespace == "new"
