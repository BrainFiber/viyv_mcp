# decorators.py
# Decorators wrapping mcp decorators
import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, Iterable, Optional, Union

from starlette.types import ASGIApp
from fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from viyv_mcp.app.entry_registry import add_entry
from viyv_mcp.agent_runtime import (
    set_tools as _rt_set_tools,
    reset_tools as _rt_reset_tools,
)

# --------------------------------------------------------------------------- #
# 内部ユーティリティ                                                          #
# --------------------------------------------------------------------------- #
def _get_mcp_from_stack() -> FastMCP:
    """
    call-stack から FastMCP インスタンスを探す。

    * register(mcp) 内 …… ローカル変数 ``mcp``
    * core.ViyvMCP 内 …… ``self._mcp`` 属性
    """
    for frame in inspect.stack():
        loc = frame.frame.f_locals

        # A. register(mcp) パターン
        mcp_obj = loc.get("mcp")
        if isinstance(mcp_obj, FastMCP):
            return mcp_obj

        # B. self._mcp パターン
        self_obj = loc.get("self")
        if (
            self_obj is not None
            and hasattr(self_obj, "_mcp")
            and isinstance(getattr(self_obj, "_mcp"), FastMCP)
        ):
            return getattr(self_obj, "_mcp")

    raise RuntimeError("FastMCP instance not found in call-stack")


async def _collect_tools_map(
    mcp: FastMCP,
    use_tools: Optional[Iterable[str]],
    exclude_tools: Optional[Iterable[str]],
) -> Dict[str, Any]:
    """use_tools / exclude_tools 指定に従って tools マップを生成"""
    registered: Dict[str, Any] = {
        info.name: info for info in mcp._tool_manager.list_tools()
    }
    targets = (
        set(use_tools)
        if use_tools is not None
        else set(registered) - set(exclude_tools or [])
    )

    async def _make_caller(tname: str):
        info = registered.get(tname)

        # 1. ローカル関数ツール
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

        # 2. RPC 経由
        if hasattr(mcp, "call_tool"):

            async def _rpc(**kw):
                res = await mcp.call_tool(tname, arguments=kw)
                if isinstance(res, CallToolResult) and res.content:
                    first = res.content[0]
                    if isinstance(first, TextContent):
                        return first.text
                return res

            _rpc.__doc__ = info.description if info else ""
            return _rpc

        raise RuntimeError(f"Tool '{tname}' not found")

    return {n: await _make_caller(n) for n in targets}


def _inject_tools_middleware(asgi_app: ASGIApp, tools_map: Dict[str, Any]) -> ASGIApp:
    """各リクエストで tools_map を ContextVar にセットするミドルウェア"""

    async def _wrapper(scope, receive, send):
        token = _rt_set_tools(tools_map)
        try:
            await asgi_app(scope, receive, send)
        finally:
            _rt_reset_tools(token)

    return _wrapper


def _wrap_callable_with_tools(
    fn: Callable[..., Any],
    mcp: FastMCP,
    use_tools: Optional[Iterable[str]],
    exclude_tools: Optional[Iterable[str]],
) -> Callable[..., Any]:
    """通常関数 / agent 用ラッパー"""

    async def _impl(*args, **kwargs):
        tools_map = await _collect_tools_map(mcp, use_tools, exclude_tools)
        token = _rt_set_tools(tools_map)
        try:
            if "tools" in inspect.signature(fn).parameters:
                kwargs["tools"] = tools_map
            return await fn(*args, **kwargs) if inspect.iscoroutinefunction(fn) else fn(
                *args, **kwargs
            )
        finally:
            _rt_reset_tools(token)

    functools.update_wrapper(_impl, fn)
    return _impl


def _wrap_factory_with_tools(
    factory: Callable[..., ASGIApp],
    mcp: FastMCP,
    use_tools: Optional[Iterable[str]],
    exclude_tools: Optional[Iterable[str]],
) -> Callable[..., ASGIApp]:
    """
    Entry 用ファクトリラッパー

    1. tools_map を生成
    2. factory(**kwargs) で ASGI アプリ作成（必要なら tools を渡す）
    3. ASGI アプリへミドルウェアを追加
    """
    wants_tools = "tools" in inspect.signature(factory).parameters

    def _factory_wrapper(*args, **kwargs):
        tools_map = asyncio.run(_collect_tools_map(mcp, use_tools, exclude_tools))

        if wants_tools:
            kwargs["tools"] = tools_map

        asgi_app = factory(*args, **kwargs)
        return _inject_tools_middleware(asgi_app, tools_map)

    functools.update_wrapper(_factory_wrapper, factory)
    return _factory_wrapper


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


# --------------------------------------------------------------------------- #
# entry デコレータ                                                             #
# --------------------------------------------------------------------------- #
def entry(
    path: str,
    *,
    use_tools: Optional[Iterable[str]] = None,
    exclude_tools: Optional[Iterable[str]] = None,
):
    """
    指定パスに Mount されるエントリポイントを登録する。

    * use_tools / exclude_tools で agent と同様にツール注入が可能
    """
    if use_tools and exclude_tools:
        raise ValueError("use_tools と exclude_tools は同時指定できません")

    def decorator(target: Union[ASGIApp, Callable[..., ASGIApp]]):
        try:
            mcp = _get_mcp_from_stack()
        except RuntimeError:
            # register(mcp) 外 … ツールが要らない or 後でラップ不可能
            add_entry(path, target)
            return target

        if callable(target):
            target = _wrap_factory_with_tools(target, mcp, use_tools, exclude_tools)
        else:
            tools_map = asyncio.run(
                _collect_tools_map(mcp, use_tools, exclude_tools)
            )
            target = _inject_tools_middleware(target, tools_map)

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

        _agent_impl = _wrap_callable_with_tools(
            fn, mcp, use_tools, exclude_tools
        )

        _agent_impl.__viyv_agent__ = True
        mcp.tool(name=tool_name, description=tool_desc)(_agent_impl)
        return fn

    return decorator