"""WebSocket bridge protocol models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AuthMessage(BaseModel):
    """Chrome extension -> server: authenticate with key."""
    type: Literal['auth'] = 'auth'
    key: str


class AuthResult(BaseModel):
    """Server -> Chrome extension: auth result."""
    type: Literal['auth_result'] = 'auth_result'
    success: bool
    error: str | None = None


class ToolCallMessage(BaseModel):
    """Server -> Chrome extension: invoke a browser tool."""
    type: Literal['tool_call'] = 'tool_call'
    id: str
    agentId: str = 'cloud'
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    timestamp: int = 0


class ToolResultMessage(BaseModel):
    """Chrome extension -> server: tool execution result."""
    type: Literal['tool_result'] = 'tool_result'
    id: str
    agentId: str = 'cloud'
    success: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    timestamp: int = 0


class PingMessage(BaseModel):
    type: Literal['ping'] = 'ping'


class PongMessage(BaseModel):
    type: Literal['pong'] = 'pong'
