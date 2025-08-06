# decorators.py
# Decorators wrapping mcp decorators
import asyncio, functools, inspect
from typing import (
    Any, Callable, Dict, Iterable, Optional, Union, Set,
    get_origin, get_args, Annotated            # ←★ add
)

from starlette.types import ASGIApp
from fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from viyv_mcp.app.entry_registry import add_entry
from viyv_mcp.agent_runtime import (
    set_tools as _rt_set_tools,
    reset_tools as _rt_reset_tools,
)

try:                                         
    from agents import RunContextWrapper
except ImportError:
    RunContextWrapper = None

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
        info.name: info for info in await mcp._tool_manager.list_tools()
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
            local_fn = getattr(info.fn, "__original_tool_fn__", info.fn)
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

# --------------------------------------------------------------------------- #
# Middleware (各リクエスト時に最新ツールを取得)                               #
# --------------------------------------------------------------------------- #
def _dynamic_tools_middleware(
    asgi_app: ASGIApp,
    mcp: FastMCP,
    collect_kwargs: Dict[str, Any],
) -> ASGIApp:
    """毎リクエストで最新ツールマップを取得し ContextVar に注入するミドルウェア"""

    async def _wrapper(scope, receive, send):
        tools_map = await _collect_tools_map(mcp, **collect_kwargs)
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
    """
    tools_map を ContextVar に流し込み、wrapper (RunContextWrapper[...]) を
    Agents SDK へ渡しつつ、FastMCP 側の JSON-Schema 生成エラーを回避するラッパ。
    """

    # ---------- RunContextWrapper 判定 ----------------------------------
    def _is_wrapper(param: inspect.Parameter) -> bool:
        if RunContextWrapper is None:
            return False
        ann = param.annotation
        if ann is inspect._empty:
            return False

        if get_origin(ann) is Annotated:            # Annotated[RCW[…], …] を剥がす
            ann = get_args(ann)[0]

        if ann is RunContextWrapper or get_origin(ann) is RunContextWrapper:
            return True
        if get_origin(ann) is Union:
            return any(
                a is RunContextWrapper or get_origin(a) is RunContextWrapper
                for a in get_args(ann)
            )
        return False

    # ---------- ラッパ本体 ----------------------------------------------
    async def _impl(*args, **kwargs):
        tools_map = await _collect_tools_map(mcp, **collect_kwargs)
        token = _rt_set_tools(tools_map)
        try:
            if "tools" in inspect.signature(fn).parameters:
                kwargs["tools"] = tools_map
            
            # wrapperパラメータが存在する場合、RunContextWrapperインスタンスを作成
            fn_sig = inspect.signature(fn)
            if any(_is_wrapper(p) for p in fn_sig.parameters.values()):
                # RunContextWrapperのインスタンスを作成
                if RunContextWrapper is not None:
                    from viyv_mcp.run_context import RunContext
                    wrapper_instance = RunContextWrapper[RunContext](None)  # type: ignore
                    # 最初の引数として追加
                    if args:
                        args = (wrapper_instance,) + args
                    else:
                        # または kwargs に追加
                        for param_name, param in fn_sig.parameters.items():
                            if _is_wrapper(param):
                                kwargs[param_name] = wrapper_instance
                                break
            
            return (
                await fn(*args, **kwargs)
                if inspect.iscoroutinefunction(fn)
                else fn(*args, **kwargs)
            )
        finally:
            _rt_reset_tools(token)

    functools.update_wrapper(_impl, fn)

    # ---------- シグネチャ再構築 ----------------------------------------
    orig_sig = inspect.signature(fn)

    # 1) wrapper パラメータを作成
    wrapper_ann = RunContextWrapper if RunContextWrapper else Any
    wrapper_param = inspect.Parameter(
        name="wrapper",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=wrapper_ann,
        default=inspect._empty,                     # 必須扱い
    )

    # 2) 元関数のパラメータ（wrapper は除外）
    other_params = [
        p for p in orig_sig.parameters.values() if not _is_wrapper(p)
    ]

    # 3) 新しいシグネチャ  (wrapper を先頭に)
    _impl.__signature__ = inspect.Signature([wrapper_param] + other_params)  # type: ignore[attr-defined]

    return _impl


def _wrap_factory_with_tools(                        # ← 差し替え
    factory: Callable[..., ASGIApp],
    mcp: FastMCP,
    **collect_kwargs,
) -> Callable[..., ASGIApp]:
    """Entry 用ファクトリラッパー（毎リクエストでツール更新）"""

    wants_tools = "tools" in inspect.signature(factory).parameters

    def _factory_wrapper(*args, **kwargs):
        init_tools_map = asyncio.run(_collect_tools_map(mcp, **collect_kwargs))
        if wants_tools:
            kwargs["tools"] = init_tools_map

        asgi_app = factory(*args, **kwargs)
        return _dynamic_tools_middleware(asgi_app, mcp, collect_kwargs)

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
    """
    * wrapper (RunContextWrapper) を **Agents 実行時** だけ受け取りたい。
    * FastMCP に登録するときは JSON-Schema 生成を壊さないよう
      wrapper をシグネチャから外したダミーを登録する。
    """

    def decorator(fn: Callable[..., Any]):
        mcp = _get_mcp_from_stack()
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or f"Viyv tool '{tool_name}'")

        # 1) Agents 実行用：wrapper を先頭に差し込む
        impl = _wrap_callable_with_tools(fn, mcp)   # ← wrapper 必須で返る

        # 2) FastMCP / JSON-Schema 用：wrapper を除いたダミー関数
        async def _schema_stub(*args, **kwargs):
            # → そのまま本体を呼び出すだけ
            return await impl(*args, **kwargs) if inspect.iscoroutinefunction(impl) else impl(*args, **kwargs)

        #   シグネチャから wrapper を削除
        orig_sig = inspect.signature(impl)
        params_no_wrapper = [
            inspect.Parameter(
                p.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=p.annotation,
                default=p.default,
            )
            for p in orig_sig.parameters.values()
            if p.name != "wrapper"
        ]
        _schema_stub.__signature__ = inspect.Signature(params_no_wrapper)  # type: ignore[attr-defined]

        # ── ★ ここが今回の追加ポイント ★ ─────────────────────
        # get_type_hints() が参照する __annotations__ を補完
        _schema_stub.__annotations__ = {
            p.name: p.annotation
            for p in params_no_wrapper
            if p.annotation is not inspect._empty
        }
        # 戻り値型があればコピー
        if orig_sig.return_annotation is not inspect._empty:
            _schema_stub.__annotations__["return"] = orig_sig.return_annotation
        # ──────────────────────────────────────────────

        _schema_stub.__doc__ = tool_desc
        #   Agents から参照できるよう実体を保持
        _schema_stub.__original_tool_fn__ = impl       # ← ここがポイント

        # 3) FastMCP に登録（JSON-Schema 生成は stub を見る）
        mcp.tool(name=tool_name, description=tool_desc, tags=tags)(_schema_stub)
        return fn  # 元の関数をそのまま返す

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
    if (use_tools and exclude_tools) or (use_tags and exclude_tags):
        raise ValueError("include と exclude を同時指定できません")

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
            target = _dynamic_tools_middleware(target, mcp, collect_kwargs)

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
        raise ValueError("include と exclude を同時指定できません")

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

        # --- 実体（wrapper 混入版） ----------
        _agent_impl = _wrap_callable_with_tools(fn, mcp, **collect_kwargs)
        _agent_impl.__viyv_agent__ = True

        # --- JSON-Schema 生成用スタブ ----------
        async def _schema_stub(*args, **kwargs):
            # wrapper を受け取らないダミー
            return await _agent_impl(*args, **kwargs)

        orig_sig = inspect.signature(_agent_impl)
        params_no_wrapper = [
            inspect.Parameter(
                p.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=p.annotation,
                default=p.default,
            )
            for p in orig_sig.parameters.values()
            if p.name != "wrapper"
        ]
        _schema_stub.__signature__ = inspect.Signature(params_no_wrapper)  # type: ignore[attr-defined]
        _schema_stub.__annotations__ = {
            p.name: p.annotation
            for p in params_no_wrapper
            if p.annotation is not inspect._empty
        }
        if orig_sig.return_annotation is not inspect._empty:
            _schema_stub.__annotations__["return"] = orig_sig.return_annotation
        _schema_stub.__doc__ = tool_desc
        _schema_stub.__original_tool_fn__ = _agent_impl

        # --- FastMCP 登録 --------------------
        mcp.tool(name=tool_name, description=tool_desc)(_schema_stub)
        return fn

    return decorator