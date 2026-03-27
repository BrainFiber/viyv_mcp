"""Tests for ToolSecurityRegistry."""

from viyv_mcp.app.security.domain.models import ToolSecurityMeta
from viyv_mcp.app.security.tool_registry import ToolSecurityRegistry


def test_register_and_get():
    reg = ToolSecurityRegistry()
    meta = ToolSecurityMeta(namespace="hr", security_level=1)
    reg.register("query_salary", meta)
    assert reg.get("query_salary") == meta


def test_get_default():
    reg = ToolSecurityRegistry()
    meta = reg.get("nonexistent")
    assert meta.namespace == "common"
    assert meta.security_level is None


def test_unregister():
    reg = ToolSecurityRegistry()
    reg.register("tool1", ToolSecurityMeta(namespace="hr"))
    reg.unregister("tool1")
    assert reg.get("tool1").namespace == "common"


def test_get_all():
    reg = ToolSecurityRegistry()
    reg.register("a", ToolSecurityMeta(namespace="x"))
    reg.register("b", ToolSecurityMeta(namespace="y"))
    all_meta = reg.get_all()
    assert len(all_meta) == 2
    assert "a" in all_meta
    assert "b" in all_meta


def test_overwrite():
    reg = ToolSecurityRegistry()
    reg.register("t", ToolSecurityMeta(namespace="old"))
    reg.register("t", ToolSecurityMeta(namespace="new"))
    assert reg.get("t").namespace == "new"
