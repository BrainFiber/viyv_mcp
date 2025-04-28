"""
Runtime helpers for agent execution.
"""

import contextvars
from typing import Dict, Callable, Coroutine

_current_tools: contextvars.ContextVar[
    Dict[str, Callable[..., Coroutine]]
] = contextvars.ContextVar("_current_tools", default={})


def set_tools(tools_map: Dict[str, Callable[..., Coroutine]]) -> contextvars.Token:
    """
    ContextVar へ現在の tools マッピングをセットし、Token を返す。
    呼び出し元は finally で reset(token) すること。
    """
    return _current_tools.set(tools_map)


def reset_tools(token: contextvars.Token) -> None:
    _current_tools.reset(token)


def get_tools() -> Dict[str, Callable[..., Coroutine]]:
    return _current_tools.get()