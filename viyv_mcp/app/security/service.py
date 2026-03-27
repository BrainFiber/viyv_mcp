"""Application-layer service orchestrating authentication, authorization, and audit."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from viyv_mcp.app.security.domain.models import (
    AgentIdentity,
    AuthMode,
    AuthResult,
)
from viyv_mcp.app.security.domain.policy import (
    authorize_tool_access,
    compute_trusted_namespaces,
)
from viyv_mcp.app.security.infrastructure.audit_writer import emit_audit_record
from viyv_mcp.app.security.infrastructure.config_loader import SecurityConfig
from viyv_mcp.app.security.infrastructure.jwt_codec import (
    JWTDecodeError,
    JWTExpiredError,
    decode_jwt,
)
from viyv_mcp.app.security.domain.models import ToolMetadataProvider

logger = logging.getLogger(__name__)


class SecurityService:
    """Single entry-point consumed by the MCP handlers and ASGI layer."""

    def __init__(
        self,
        config: SecurityConfig,
        tool_registry: ToolMetadataProvider,
        audit_logger: logging.Logger,
    ) -> None:
        self._config = config
        self._tool_registry = tool_registry
        self._audit_logger = audit_logger
        self.stdio_identity: AgentIdentity | None = None

    # -- properties ------------------------------------------------------

    @property
    def auth_mode(self) -> AuthMode:
        return self._config.auth_mode

    @property
    def is_bypass(self) -> bool:
        return self._config.auth_mode == AuthMode.BYPASS

    # -- authentication --------------------------------------------------

    def authenticate_token(self, token: str) -> AgentIdentity:
        """Decode and validate *token*, returning an :class:`AgentIdentity`.

        Raises :class:`JWTDecodeError` / :class:`JWTExpiredError` on failure.
        """
        payload = decode_jwt(
            token,
            self._config.jwt_secret,
            algorithm=self._config.jwt_algorithm,
            issuer=self._config.jwt_issuer,
            audience=self._config.jwt_audience,
        )

        # Required claims
        for claim in ("sub", "namespace"):
            if claim not in payload:
                raise JWTDecodeError(f"Missing required JWT claim: {claim}")

        # Coerce trust to tuple of strings
        raw_trust = payload.get("trust", [])
        if not isinstance(raw_trust, list):
            raw_trust = []
        trust = tuple(str(t) for t in raw_trust)

        # clearance: int | None (missing = lowest privilege)
        raw_clearance = payload.get("clearance")
        if raw_clearance is not None:
            try:
                clearance: int | None = int(raw_clearance)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid clearance value in JWT: {raw_clearance!r}, treating as None"
                )
                clearance = None
        else:
            clearance = None

        return AgentIdentity(
            sub=str(payload["sub"]),
            clearance=clearance,
            namespace=str(payload["namespace"]),
            trust=trust,
        )

    # -- authorization ---------------------------------------------------

    def authorize_tool_call(
        self, agent: AgentIdentity, tool_name: str
    ) -> AuthResult:
        meta = self._tool_registry.get(tool_name)
        trusted_ns = compute_trusted_namespaces(
            agent,
            implicit_trust_common=self._config.implicit_trust_common,
        )
        return authorize_tool_access(
            agent,
            meta.namespace,
            meta.security_level,
            trusted_namespaces=trusted_ns,
        )

    def filter_tools_for_agent(
        self, agent: AgentIdentity, tools: Sequence[Any]
    ) -> list[Any]:
        """Return only the tools visible to *agent* based on namespace.

        Note: this deliberately filters by **namespace only**, not clearance.
        The design separates visibility (namespace → tools/list) from
        executability (clearance → tools/call).  An agent can *see* a tool
        it cannot *call*, which lets the LLM know the tool exists and
        request elevated access if needed.
        """
        trusted_ns = compute_trusted_namespaces(
            agent,
            implicit_trust_common=self._config.implicit_trust_common,
        )
        result: list[Any] = []
        for tool in tools:
            name = getattr(tool, "name", None)
            if name is None:
                logger.warning(f"Security: tool object without 'name' attribute skipped: {tool!r}")
                continue
            meta = self._tool_registry.get(name)
            if meta.namespace in trusted_ns:
                result.append(tool)
        return result

    # -- audit -----------------------------------------------------------

    def log_access(
        self,
        agent: AgentIdentity | None,
        tool_name: str,
        result: AuthResult,
        *,
        mode: str = "",
    ) -> None:
        meta = self._tool_registry.get(tool_name)
        record: dict[str, Any] = {
            "agent": agent.sub if agent else None,
            "agent_ns": agent.namespace if agent else None,
            "clearance": agent.clearance if agent else None,
            "tool": tool_name,
            "tool_ns": meta.namespace,
            "tool_level": meta.security_level,
            "result": "allowed" if result.allowed else "denied",
        }
        if not result.allowed:
            record["reason"] = result.reason
        if mode:
            record["mode"] = mode
        emit_audit_record(self._audit_logger, record)

    def log_bypass_access(self, tool_name: str) -> None:
        emit_audit_record(
            self._audit_logger,
            {"agent": "bypass", "tool": tool_name, "result": "allowed", "mode": "bypass"},
        )
