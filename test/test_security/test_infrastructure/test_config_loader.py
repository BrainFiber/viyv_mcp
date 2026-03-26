"""Tests for config loading and validation."""

import os

import pytest

from viyv_mcp.app.security.domain.models import AuthMode
from viyv_mcp.app.security.infrastructure.config_loader import (
    SecurityConfig,
    load_security_config,
    validate_config,
)


def test_defaults():
    config = SecurityConfig()
    assert config.auth_mode == AuthMode.DENY_ALL
    assert config.implicit_trust_common is True
    assert "public" in config.security_levels


def test_security_levels_from_list():
    config = SecurityConfig(
        security_levels=[{"name": "low", "rank": 0}, {"name": "high", "rank": 1}]
    )
    assert config.security_levels == {"low": 0, "high": 1}


def test_validate_bypass_production(monkeypatch):
    config = SecurityConfig(auth_mode=AuthMode.BYPASS, env_name="production")
    with pytest.raises(SystemExit):
        validate_config(config)


def test_validate_bypass_non_production():
    config = SecurityConfig(auth_mode=AuthMode.BYPASS, env_name="staging")
    validate_config(config)  # should not raise


def test_validate_authenticated_no_secret():
    config = SecurityConfig(auth_mode=AuthMode.AUTHENTICATED, jwt_secret="")
    with pytest.raises(SystemExit):
        validate_config(config)


def test_load_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VIYV_MCP_AUTH", "bypass")
    monkeypatch.setenv("VIYV_MCP_JWT_SECRET", "s3cret")
    monkeypatch.setenv("VIYV_SECURITY_CONFIG", str(tmp_path / "nonexistent.yaml"))
    config = load_security_config()
    assert config.auth_mode == AuthMode.BYPASS
    assert config.jwt_secret == "s3cret"


def test_load_auto_detect_authenticated(monkeypatch, tmp_path):
    monkeypatch.delenv("VIYV_MCP_AUTH", raising=False)
    monkeypatch.setenv("VIYV_MCP_JWT_SECRET", "mysecret")
    monkeypatch.setenv("VIYV_SECURITY_CONFIG", str(tmp_path / "nonexistent.yaml"))
    config = load_security_config()
    assert config.auth_mode == AuthMode.AUTHENTICATED
