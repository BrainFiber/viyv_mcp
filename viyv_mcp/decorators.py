# Decorators wrapping mcp decorators
import functools
import inspect
from typing import Any, Callable, Coroutine, Dict, Iterable, List, Optional

from viyv_mcp.app.entry_registry import add_entry
from starlette.types import ASGIApp
from typing import Callable, Union

from viyv_mcp.agent_runtime import (
    get_tools as _rt_get_tools,
    set_tools as _rt_set_tools,
    reset_tools as _rt_reset_tools,
)
from mcp.types import CallToolResult, TextContent
from fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# 内部ユーティリティ
# --------------------------------------------------------------------------- #
def _get_mcp_from_stack() -> FastMCP:
    """register(mcp) 内の call-stack から FastMCP インスタンスを取得"""
    for frame_info in inspect.stack():
        local = frame_info.frame.f_locals
        if "mcp" in local and isinstance(local["mcp"], FastMCP):
            return local["mcp"]
    raise RuntimeError("viyv decorator must be used inside register(mcp)")


# --------------------------------------------------------------------------- #
# 基本デコレータ (tool / resource / prompt)                                  #
# --------------------------------------------------------------------------- #
def tool(name: str | None = None, description: str | None = None):
    def decorator(fn: Callable):
        _get_mcp_from_stack().tool(name=name, description=description)(fn)
        return fn
    return decorator


def resource(
    uri: str,
    name: str | None = None,
    description: str | None = None,
    mime_type: str | None = None,
):
    def decorator(fn: Callable):
        _get_mcp_from_stack().resource(
            uri, name=name, description=description, mime_type=mime_type
        )(fn)
        return fn
    return decorator


def prompt(name: str | None = None, description: str | None = None):
    def decorator(fn: Callable):
        _get_mcp_from_stack().prompt(name=name, description=description)(fn)
        return fn
    return decorator

def entry(path: str):
    """
    指定パスに Mount されるエントリポイントを登録する。
    引数は (1) ASGI アプリインスタンス  か (2) ASGI アプリを返すファクトリ。
    """
    def decorator(target: Union[ASGIApp, Callable[[], ASGIApp]]):
        add_entry(path, target)
        return target
    return decorator

# --------------------------------------------------------------------------- #
# agent デコレータ                                                             #
# --------------------------------------------------------------------------- #
def agent(
    *,
    name: str | None = None,
    description: str | None = None,
    use_tools: Optional[Iterable[str]] = None,
    exclude_tools: Optional[Iterable[str]] = None,
):
    if use_tools and exclude_tools:
        raise ValueError("use_tools と exclude_tools は同時指定できません")

    def decorator(fn: Callable[..., Any]):
        mcp = _get_mcp_from_stack()
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "Viyv Agent")

        # ---------------------------- agent が実際に呼ばれる ASGI 関数 ---- #
        async def _agent_impl(*args, **kwargs):
            # 1️⃣ 現在登録されているローカル FastMCP ツール一覧
            registered: Dict[str, Any] = {
                info.name: info for info in mcp._tool_manager.list_tools()
            }

            # 2️⃣ 対象ツール集合
            targets = (
                set(use_tools)
                if use_tools
                else set(registered) - set(exclude_tools or [])
            )

            # 3️⃣ FastMCP ツールを呼び出すラッパ生成
            async def _make_caller(tname: str):
                info = registered.get(tname)

                # 3-A. ローカル関数ツール
                if info and getattr(info, "fn", None):
                    local_fn = info.fn
                    sig = inspect.signature(local_fn)

                    if inspect.iscoroutinefunction(local_fn):

                        async def _async_wrapper(**kw):
                            return await local_fn(**kw)

                        _async_wrapper.__signature__ = sig  # type: ignore[attr-defined]
                        _async_wrapper.__doc__ = local_fn.__doc__ or info.description
                        return _async_wrapper

                    async def _sync_wrapper(**kw):
                        return local_fn(**kw)

                    _sync_wrapper.__signature__ = sig      # type: ignore[attr-defined]
                    _sync_wrapper.__doc__ = local_fn.__doc__ or info.description
                    return _sync_wrapper

                # 3-B. RPC で呼び出す
                if hasattr(mcp, "call_tool"):

                    async def _rpc(**kw):
                        res = await mcp.call_tool(tname, arguments=kw)
                        if isinstance(res, CallToolResult) and res.content:
                            first = res.content[0]
                            if isinstance(first, TextContent):
                                return first.text
                        return res

                    _rpc.__signature__ = inspect.Signature(
                        parameters=[
                            inspect.Parameter(n, inspect.Parameter.KEYWORD_ONLY)
                            for n in kw.keys()
                        ]
                    )
                    _rpc.__doc__ = info.description if info else ""
                    return _rpc

                raise RuntimeError(f"Tool '{tname}' not found")

            tools_map = {n: await _make_caller(n) for n in targets}

            # 4️⃣ ContextVar セット
            token = _rt_set_tools(tools_map)
            try:
                if "tools" in inspect.signature(fn).parameters:
                    kwargs["tools"] = tools_map
                return await fn(*args, **kwargs) if inspect.iscoroutinefunction(fn) else fn(
                    *args, **kwargs
                )
            finally:
                _rt_reset_tools(token)

        functools.update_wrapper(_agent_impl, fn)
        _agent_impl.__viyv_agent__ = True
        mcp.tool(name=tool_name, description=tool_desc)(_agent_impl)
        return fn

    return decorator