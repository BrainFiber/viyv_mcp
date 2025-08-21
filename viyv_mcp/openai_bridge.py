# File: viyv_mcp/openai_bridge.py
"""
FastMCP ⇄ OpenAI Agents SDK ブリッジ

* `default` キーは最終 JSON-Schema から完全に除去
* OpenAI Functions 仕様に合わせ **required = properties の全キー**
* 既定値を持つ引数は `nullable:true`
* RunContextWrapper[...] 型パラメータは JSON-Schema から除外
"""
from __future__ import annotations

import inspect
from typing import (
    Annotated,
    Callable,
    Coroutine,
    Dict,
    Iterable,
    List,
    Optional,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from viyv_mcp.agent_runtime import get_tools

# ──────────────────────────────── SDK 遅延 import ────────────────────────────────
try:
    from agents import function_tool, RunContextWrapper  # type: ignore
except ImportError:  # pragma: no cover
    function_tool = None
    RunContextWrapper = None  # type: ignore


def _ensure_function_tool():
    global function_tool
    if function_tool is None:
        from agents import function_tool as _ft  # noqa: E402
        function_tool = _ft
    return function_tool


# ───────────────────────────── sync → async ラッパ ─────────────────────────────
def _as_async(fn: Callable) -> Callable[..., Coroutine]:
    if inspect.iscoroutinefunction(fn):
        return fn  # type: ignore
    async def _wrapper(**kw):
        return fn(**kw)
    _wrapper.__signature__ = inspect.signature(fn)  # type: ignore
    _wrapper.__doc__ = fn.__doc__
    return _wrapper


# ─────────────────────── Pydantic ラッパ（nullable=true） ──────────────────────
# ─────────────────────── Pydantic ラッパ（nullable=true） ──────────────────────
def _wrap_with_pydantic(call_fn: Callable) -> Callable[..., Coroutine]:
    """
    * 非 wrapper パラメータは Pydantic で検証
    * RunContextWrapper[...] は JSON-Schema から除外しつつ
      **関数シグネチャの先頭の位置引数** として残す  
      （Agents SDK がコンテキストを自動注入できるようにする）
    """
    orig_sig = inspect.signature(call_fn)
    param_names = list(orig_sig.parameters)
    fields: Dict[str, tuple] = {}
    fallback_ann = Union[int, float, str, bool, None]

    # ------------- RunContextWrapper 判定 --------------------------------
    def _is_wrapper(param: inspect.Parameter) -> bool:
        if RunContextWrapper is None:
            return False
        ann = param.annotation
        if ann is inspect._empty:
            return False
        # Annotated[RCW[...], ...] → 中身を剥がす
        if get_origin(ann) is Annotated:
            ann = get_args(ann)[0]
        if ann is RunContextWrapper or get_origin(ann) is RunContextWrapper:
            return True
        if get_origin(ann) is Union:
            return any(
                a is RunContextWrapper or get_origin(a) is RunContextWrapper
                for a in get_args(ann)
            )
        return False

    # ------------- ArgsModel 用フィールド構築 ----------------------------
    for name, param in orig_sig.parameters.items():
        if _is_wrapper(param):
            continue  # wrapper → JSON-Schema へは出さない
        ann_base = (
            param.annotation if param.annotation is not inspect._empty else fallback_ann
        )
        if param.default is inspect._empty:
            fields[name] = (ann_base, Field(..., title=name))
        else:
            fields[name] = (
                ann_base,
                Field(None, title=name, json_schema_extra={"nullable": True}),
            )

    ArgsModel: type[BaseModel] = create_model(          # type: ignore
        f"{call_fn.__name__}_args",
        __config__=ConfigDict(                          # ★ Pydantic v2スタイル
            extra="forbid",
            arbitrary_types_allowed=True,  # ← 独自型を許可
        ),
        **fields,
    )

    # ------------- 新しい Signature 構築 ---------------------------------
    new_params: List[inspect.Parameter] = []
    wrapper_names: List[str] = []

    # ① wrapper を先頭に POSITIONAL_OR_KEYWORD で追加
    for p in orig_sig.parameters.values():
        if _is_wrapper(p):
            wrapper_names.append(p.name)
            new_params.append(
                inspect.Parameter(
                    p.name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=p.annotation,
                    default=(p.default if p.default is not inspect._empty else None),
                )
            )

    # ② 他パラメータを keyword-only で追加
    for p in orig_sig.parameters.values():
        if _is_wrapper(p):
            continue
        new_params.append(
            inspect.Parameter(
                p.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=fields[p.name][0],
                default=(inspect._empty if p.default is inspect._empty else None),
            )
        )

    new_sig = inspect.Signature(new_params)

    # ------------- バリデーション関数 ------------------------------------
    async def _validated(*args, **kwargs):
        # a) wrapper を位置引数から取得
        wrapper_kw = {}
        if wrapper_names:
            for idx, wname in enumerate(wrapper_names):
                if idx < len(args):
                    wrapper_kw[wname] = args[idx]
            args = args[len(wrapper_names):]

        # b) wrapper が kwargs に来た場合も取り出す
        for wname in wrapper_names:
            if wname in kwargs:
                wrapper_kw[wname] = kwargs.pop(wname)

        # c) 残り位置引数 → kwargs へマッピング
        if args:
            if kwargs:
                raise TypeError("位置・キーワード引数を同時指定できません")
            if len(args) == 1 and isinstance(args[0], dict):
                kwargs = dict(args[0])
            elif len(args) == len(
                [n for n in param_names if n not in wrapper_kw]
            ):
                kwargs = {
                    [n for n in param_names if n not in wrapper_kw][i]: arg
                    for i, arg in enumerate(args)
                }
            else:
                raise TypeError("無効な位置引数数")

        # d) Pydantic 検証
        try:
            model = ArgsModel(**kwargs)
        except ValidationError as e:
            raise ValueError(f"引数バリデーション失敗: {e}") from e

        clean_kwargs = model.model_dump()

        # e) デフォルト補完
        for n, p in orig_sig.parameters.items():
            if (
                n not in clean_kwargs
                and n not in wrapper_kw
                and p.default is not inspect._empty
            ):
                clean_kwargs[n] = p.default

        # f) wrapper を戻す
        clean_kwargs.update(wrapper_kw)
        return await call_fn(**clean_kwargs)

    _validated.__signature__ = new_sig  # type: ignore
    _validated.__doc__ = call_fn.__doc__
    return _validated


# ─────────────── default キーを strip ───────────────
def _strip_default(obj):
    if isinstance(obj, dict):
        return {k: _strip_default(v) for k, v in obj.items() if k != "default"}
    if isinstance(obj, list):
        return [_strip_default(x) for x in obj]
    return obj


# ─────────────────────────── build_function_tools ───────────────────────────
def build_function_tools(
    *,
    use_tools: Iterable[str] | None = None,
    exclude_tools: Iterable[str] | None = None,
) -> List[Callable]:
    tools_dict: Dict[str, Callable] = get_tools()
    if not tools_dict:
        raise RuntimeError("No FastMCP tools available in current context")

    selected = (
        {n: tools_dict[n] for n in use_tools if n in tools_dict}
        if use_tools
        else dict(tools_dict)
    )
    if exclude_tools:
        for n in exclude_tools:
            selected.pop(n, None)
    if not selected:
        raise ValueError("フィルタリング結果が 0 件")

    ft = _ensure_function_tool()
    oa_tools: List[Callable] = []

    for tname, call_fn in selected.items():
        async_fn = _as_async(call_fn)
        validated_fn = _wrap_with_pydantic(async_fn)
        tool = ft(
            name_override=tname,
            description_override=(validated_fn.__doc__ or tname),
            strict_mode=False,
        )(validated_fn)

        schema = _strip_default(tool.params_json_schema)
        props = schema.get("properties", {})
        schema["required"] = list(props.keys()) if props else []
        tool.params_json_schema = schema
        oa_tools.append(tool)

    return oa_tools