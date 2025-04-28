"""
FastMCP ⇄ OpenAI Agents SDK ブリッジユーティリティ
"""

from __future__ import annotations

import inspect
from typing import Callable, Coroutine, Dict, Iterable, List

from viyv_mcp.agent_runtime import get_tools
from pydantic import BaseModel, ValidationError, create_model, Field

# OpenAI Agents SDK を遅延 import
try:
    from agents import function_tool  # type: ignore
except ImportError:  # pragma: no cover
    function_tool = None


def _ensure_function_tool():
    global function_tool
    if function_tool is None:
        from agents import function_tool as _ft  # noqa: E402
        function_tool = _ft
    return function_tool


# --------------------------------------------------------------------------- #
# ラッパ生成ユーティリティ
# --------------------------------------------------------------------------- #
def _as_async(fn: Callable) -> Callable[..., Coroutine]:
    """sync 関数を async ラッパで包む"""
    if inspect.iscoroutinefunction(fn):
        return fn  # type: ignore[return-value]

    async def _wrapper(**kw):
        return fn(**kw)

    _wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    _wrapper.__doc__ = fn.__doc__
    return _wrapper


def _wrap_with_pydantic(call_fn: Callable) -> Callable[..., Coroutine]:
    """
    call_fn: signature 完備 & async
    - OpenAI Agents SDK が
        * dict を 1 つの位置引数で渡す 例: fn({"a":1,"b":2})
        * 位置引数で順番に渡す      例: fn(1, 2)
      どちらにも対応。
    - Pydantic で厳密バリデーション後に call_fn を実行。
    """
    sig = inspect.signature(call_fn)
    param_names = list(sig.parameters)  # ['a', 'b', ...]
    fields: Dict[str, tuple] = {}

    for name, param in sig.parameters.items():
        ann = (
            param.annotation
            if param.annotation is not inspect._empty
            else (int | float | str | bool | None)
        )
        default_field = (
            Field(..., title=name)
            if param.default is inspect._empty
            else Field(param.default, title=name)
        )
        fields[name] = (ann, default_field)

    ArgsModel: type[BaseModel] = create_model(  # type: ignore[valid-type]
        f"{call_fn.__name__}_args",
        __config__=type("Config", (), {"extra": "forbid"}),
        **fields,
    )

    async def _validated(*args, **kwargs):
        # --- args を kwargs に変換 ------------------------------------- #
        if args:
            if kwargs:
                raise TypeError("位置引数とキーワード引数を同時には渡せません")
            # {dict} 1 個だけ → そのまま展開
            if len(args) == 1 and isinstance(args[0], dict):
                kwargs = dict(args[0])
            # 引数個数が一致 → 名前にマッピング
            elif len(args) == len(param_names):
                kwargs = {param_names[i]: arg for i, arg in enumerate(args)}
            else:
                raise TypeError(
                    f"_validated は位置引数を取りません "
                    f"(期待: 1 dict or {len(param_names)} values, 受信: {len(args)})"
                )

        try:
            model = ArgsModel(**kwargs)
        except ValidationError as e:
            raise ValueError(f"引数バリデーション失敗: {e}") from e

        return await call_fn(**model.model_dump())

    _validated.__signature__ = sig  # type: ignore[attr-defined]
    _validated.__doc__ = call_fn.__doc__
    return _validated


# --------------------------------------------------------------------------- #
# 外部公開 API
# --------------------------------------------------------------------------- #
def build_function_tools(
    *,
    use_tools: Iterable[str] | None = None,
    exclude_tools: Iterable[str] | None = None,
) -> List[Callable]:
    """
    現在 ContextVar にある FastMCP ツール群を OpenAI Agents SDK の
    function_tool に変換して返す。
    """
    if use_tools and exclude_tools:
        raise ValueError("use_tools と exclude_tools は同時指定できません")

    tools_dict: Dict[str, Callable] = get_tools()
    if not tools_dict:
        raise RuntimeError("No FastMCP tools available in current context")

    # フィルタリング
    if use_tools is not None:
        selected = {n: tools_dict[n] for n in use_tools if n in tools_dict}
    elif exclude_tools is not None:
        selected = {n: fn for n, fn in tools_dict.items() if n not in exclude_tools}
    else:
        selected = tools_dict

    ft = _ensure_function_tool()
    oa_tools: List[Callable] = []

    for tname, call_fn in selected.items():
        async_fn = _as_async(call_fn)
        validated_fn = _wrap_with_pydantic(async_fn)

        tool_obj = ft(
            name_override=tname,
            description_override=(validated_fn.__doc__ or tname),
        )(validated_fn)
        oa_tools.append(tool_obj)

    return oa_tools