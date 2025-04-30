# decorators.py
# Decorators wrapping mcp decorators
import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, Iterable, Optional, Union, Set

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
        mcp_obj = loc.get("mcp")
        if isinstance(mcp_obj, FastMCP):
            return mcp_obj

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
    *,
    use_tools: Optional[Iterable[str]] = None,
    exclude_tools: Optional[Iterable[str]] = None,
    use_tags: Optional[Iterable[str]] = None,
    exclude_tags: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    指定条件に合致するツール名 → 呼び出しラッパー の dict を返す

    - use_tools / exclude_tools … ツール名でフィルタ
    - use_tags / exclude_tags   … タグでフィルタ
    """
    registered: Dict[str, Any] = {
        info.name: info for info in mcp._tool_manager.list_tools()
    }

    # ------- ① まず候補集合を決める -------------------------------------- #
    selected: Set[str]

    if use_tools or use_tags:
        selected = set(use_tools or [])
    else:
        selected = set(registered)  # 何も指定が無ければ全ツール

    # タグによる追加
    if use_tags:
        tagset = set(use_tags)
        for name, info in registered.items():
            if tagset & set(getattr(info, "tags", set())):
                selected.add(name)

    # ---------- ② 除外フィルタ ------------------------------------------- #
    if exclude_tools:
        selected -= set(exclude_tools)

    if exclude_tags:
        ex_tagset = set(exclude_tags)
        selected = {
            n
            for n in selected
            if not (ex_tagset & set(getattr(registered[n], "tags", set())))
        }

    # ---------- ③ 呼び出しラッパー生成 ----------------------------------- #
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

    return {n: await _make_caller(n) for n in selected}


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
    **collect_kwargs,
) -> Callable[..., Any]:
    """通常関数 / agent 用ラッパー"""

    async def _impl(*args, **kwargs):
        tools_map = await _collect_tools_map(mcp, **collect_kwargs)
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
    **collect_kwargs,
) -> Callable[..., ASGIApp]:
    """Entry 用ファクトリラッパー"""

    wants_tools = "tools" in inspect.signature(factory).parameters

    def _factory_wrapper(*args, **kwargs):
        tools_map = asyncio.run(_collect_tools_map(mcp, **collect_kwargs))

        if wants_tools:
            kwargs["tools"] = tools_map

        asgi_app = factory(*args, **kwargs)
        return _inject_tools_middleware(asgi_app, tools_map)

    functools.update_wrapper(_factory_wrapper, factory)
    return _factory_wrapper


# --------------------------------------------------------------------------- #
# 基本デコレータ (tool / resource / prompt)                                  #
# --------------------------------------------------------------------------- #
def tool(
    name: str | None = None,
    description: str | None = None,
    tags: set[str] | None = None,
):
    def decorator(fn: Callable):
        _get_mcp_from_stack().tool(name=name, description=description, tags=tags)(fn)
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
    use_tags: Optional[Iterable[str]] = None,
    exclude_tags: Optional[Iterable[str]] = None,
):
    """
    指定パスに Mount されるエントリポイントを登録する。

    - ツール名 / タグの両方で include / exclude 指定が可能
    """
    if (use_tools and exclude_tools) or (use_tags and exclude_tags):
        raise ValueError("include と exclude を同じキーで同時指定できません")

    def decorator(target: Union[ASGIApp, Callable[..., ASGIApp]]):
        try:
            mcp = _get_mcp_from_stack()
        except RuntimeError:
            add_entry(path, target)
            return target

        collect_kwargs = dict(
            use_tools=use_tools,
            exclude_tools=exclude_tools,
            use_tags=use_tags,
            exclude_tags=exclude_tags,
        )

        if callable(target):
            target = _wrap_factory_with_tools(target, mcp, **collect_kwargs)
        else:
            tools_map = asyncio.run(_collect_tools_map(mcp, **collect_kwargs))
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
    use_tags: Optional[Iterable[str]] = None,
    exclude_tags: Optional[Iterable[str]] = None,
):
    if (use_tools and exclude_tools) or (use_tags and exclude_tags):
        raise ValueError("include と exclude を同じキーで同時指定できません")

    collect_kwargs = dict(
        use_tools=use_tools,
        exclude_tools=exclude_tools,
        use_tags=use_tags,
        exclude_tags=exclude_tags,
    )

    def decorator(fn: Callable[..., Any]):
        mcp = _get_mcp_from_stack()
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "Viyv Agent")

        _agent_impl = _wrap_callable_with_tools(fn, mcp, **collect_kwargs)
        _agent_impl.__viyv_agent__ = True
        mcp.tool(name=tool_name, description=tool_desc)(_agent_impl)
        return fn

    return decorator