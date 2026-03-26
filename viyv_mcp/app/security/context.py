"""ContextVar bridge between transport layers and the FastMCP middleware.

* **HTTP mode** — the ASGI JWT extractor sets the identity per-request.
* **stdio mode** — the identity is set once at startup and inherited by all
  subsequent async tasks.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from viyv_mcp.app.security.domain.models import AgentIdentity

_current_agent_identity: ContextVar[AgentIdentity | None] = ContextVar(
    "viyv_agent_identity", default=None
)


def set_agent_identity(identity: AgentIdentity | None) -> Token:
    return _current_agent_identity.set(identity)


def get_agent_identity() -> AgentIdentity | None:
    return _current_agent_identity.get()


def reset_agent_identity(token: Token) -> None:
    _current_agent_identity.reset(token)
