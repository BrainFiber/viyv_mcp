"""Tests for ContextVar bridge."""

from viyv_mcp.app.security.context import (
    get_agent_identity,
    reset_agent_identity,
    set_agent_identity,
)
from viyv_mcp.app.security.domain.models import AgentIdentity


def test_set_and_get():
    agent = AgentIdentity(sub="a", clearance="public", namespace="ns")
    token = set_agent_identity(agent)
    try:
        assert get_agent_identity() is agent
    finally:
        reset_agent_identity(token)


def test_default_is_none():
    assert get_agent_identity() is None


def test_reset():
    agent = AgentIdentity(sub="a", clearance="public", namespace="ns")
    token = set_agent_identity(agent)
    reset_agent_identity(token)
    assert get_agent_identity() is None
