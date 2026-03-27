"""Load and validate security configuration from env vars and optional YAML."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel

from viyv_mcp.app.security.domain.models import AuthMode

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """Raised when security configuration cannot be loaded."""


class SecurityConfig(BaseModel):
    """Immutable security configuration — validated by Pydantic."""

    auth_mode: AuthMode = AuthMode.DENY_ALL
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    implicit_trust_common: bool = True
    audit_log_path: str | None = None
    env_name: str | None = None

    model_config = {"frozen": True, "extra": "ignore"}


def load_security_config(yaml_path: str | None = None) -> SecurityConfig:
    """Build a :class:`SecurityConfig` from environment variables and an
    optional YAML file.

    Priority: environment variables override YAML values.
    """
    yaml_data: dict[str, Any] = {}

    # --- Optional YAML -------------------------------------------------
    resolved_path = yaml_path or os.environ.get("VIYV_SECURITY_CONFIG", "security.yaml")
    if os.path.isfile(resolved_path):
        try:
            import yaml  # PyYAML — optional dependency
        except ImportError:
            raise ConfigLoadError(
                f"security.yaml found at {resolved_path} but PyYAML is not installed. "
                "Install it with: pip install 'viyv_mcp[security]'"
            ) from None
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
        except Exception as exc:
            raise ConfigLoadError(f"Failed to parse {resolved_path}: {exc}") from exc

    # --- Environment variables (override YAML) -------------------------
    env_auth = os.environ.get("VIYV_MCP_AUTH", "").lower().strip()
    env_secret = os.environ.get("VIYV_MCP_JWT_SECRET", "")
    env_audit = os.environ.get("VIYV_MCP_AUDIT_LOG")
    env_name = os.environ.get("VIYV_MCP_ENV")

    # Determine auth_mode
    valid_modes = {m.value for m in AuthMode}
    if env_auth:
        if env_auth not in valid_modes:
            logger.warning(
                f"Security: unknown VIYV_MCP_AUTH={env_auth!r}, "
                f"valid values: {sorted(valid_modes)}. Falling back to deny_all."
            )
        auth_mode = AuthMode(env_auth) if env_auth in valid_modes else AuthMode.DENY_ALL
    elif "auth_mode" in yaml_data:
        raw = yaml_data["auth_mode"]
        if raw not in valid_modes:
            logger.warning(
                f"Security: unknown auth_mode={raw!r} in YAML, "
                f"valid values: {sorted(valid_modes)}. Falling back to deny_all."
            )
        auth_mode = AuthMode(raw) if raw in valid_modes else AuthMode.DENY_ALL
    elif env_secret or os.environ.get("VIYV_MCP_JWT"):
        auth_mode = AuthMode.AUTHENTICATED
    else:
        auth_mode = AuthMode.DENY_ALL

    # Build config
    config_kwargs: dict[str, Any] = {
        "auth_mode": auth_mode,
        "jwt_secret": env_secret or yaml_data.get("jwt_secret", ""),
        "jwt_algorithm": yaml_data.get("jwt_algorithm", "HS256"),
        "jwt_issuer": yaml_data.get("jwt_issuer"),
        "jwt_audience": yaml_data.get("jwt_audience"),
        "implicit_trust_common": yaml_data.get("implicit_trust_common", True),
        "audit_log_path": env_audit or yaml_data.get("audit_log_path"),
        "env_name": env_name,
    }

    return SecurityConfig(**config_kwargs)


def validate_config(config: SecurityConfig) -> None:
    """Raise :class:`SystemExit` if the configuration is invalid."""

    if (
        config.env_name
        and config.env_name.lower() == "production"
        and config.auth_mode == AuthMode.BYPASS
    ):
        logger.critical(
            "FATAL: bypass mode is not allowed in production. "
            "Set VIYV_MCP_AUTH to a value other than 'bypass' or remove VIYV_MCP_ENV=production."
        )
        raise SystemExit(1)

    if config.auth_mode == AuthMode.AUTHENTICATED and not config.jwt_secret:
        logger.critical(
            "FATAL: VIYV_MCP_JWT_SECRET is required when authentication is enabled."
        )
        raise SystemExit(1)
