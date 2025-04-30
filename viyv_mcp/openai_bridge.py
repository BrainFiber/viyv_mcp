"""
FastMCP ⇄ OpenAI Agents SDK ブリッジ

* `default` キーは最終 JSON-Schema から完全に除去
* OpenAI Functions の仕様に合わせて **required = properties の全キー**
* 既定値を持つ引数は `nullable: true` で表現し、実行時に補完
"""

from __future__ import annotations

import inspect
from typing import Callable, Coroutine, Dict, Iterable, List, Optional, Union

from viyv_mcp.agent_runtime import get_tools
from pydantic import BaseModel, ValidationError, create_model, Field

# ──────────────────────────────── SDK 遅延 import ──────────────────────────────── #
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


# ───────────────────────────── sync → async ラッパ ───────────────────────────── #
def _as_async(fn: Callable) -> Callable[..., Coroutine]:
    if inspect.iscoroutinefunction(fn):
        return fn  # type: ignore[return-value]

    async def _wrapper(**kw):
        return fn(**kw)

    _wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    _wrapper.__doc__ = fn.__doc__
    return _wrapper


# ─────────────────────── Pydantic ラッパ（nullable=true） ────────────────────── #
def _wrap_with_pydantic(call_fn: Callable) -> Callable[..., Coroutine]:
    """
    * 既定値を持つ param → `nullable: true`、required から外す
    * JSON-Schema に `default` を残さない
    """
    orig_sig = inspect.signature(call_fn)
    param_names = list(orig_sig.parameters)
    fields: Dict[str, tuple] = {}
    fallback_ann = Union[int, float, str, bool, None]

    for name, param in orig_sig.parameters.items():
        ann_base = param.annotation if param.annotation is not inspect._empty else fallback_ann

        if param.default is inspect._empty:  # 必須
            fields[name] = (ann_base, Field(..., title=name))
        else:  # 任意 → nullable:true
            fields[name] = (
                ann_base,
                Field(
                    None,
                    title=name,
                    json_schema_extra={"nullable": True},
                ),
            )

    ArgsModel: type[BaseModel] = create_model(  # type: ignore[valid-type]
        f"{call_fn.__name__}_args",
        __config__=type("Config", (), {"extra": "forbid"}),
        **fields,
    )

    # Signature：任意 param は default=None
    new_params = [
        inspect.Parameter(
            p.name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            annotation=fields[p.name][0],
            default=(inspect._empty if p.default is inspect._empty else None),
        )
        for p in orig_sig.parameters.values()
    ]
    new_sig = inspect.Signature(new_params)

    async def _validated(*args, **kwargs):
        # 位置引数(dict / 順序) を kwargs へ
        if args:
            if kwargs:
                raise TypeError("位置・キーワード引数を同時指定できません")
            if len(args) == 1 and isinstance(args[0], dict):
                kwargs = dict(args[0])
            elif len(args) == len(param_names):
                kwargs = {param_names[i]: arg for i, arg in enumerate(args)}
            else:
                raise TypeError("無効な位置引数数")
        try:
            model = ArgsModel(**kwargs)
        except ValidationError as e:
            raise ValueError(f"引数バリデーション失敗: {e}") from e

        clean_kwargs = model.model_dump()
        # 既定値補完
        for n, p in orig_sig.parameters.items():
            if clean_kwargs.get(n) is None and p.default is not inspect._empty:
                clean_kwargs[n] = p.default
        return await call_fn(**clean_kwargs)

    _validated.__signature__ = new_sig  # type: ignore[attr-defined]
    _validated.__doc__ = call_fn.__doc__
    return _validated


# ──────────────── default キーを再帰的に strip ──────────────── #
def _strip_default(obj):
    if isinstance(obj, dict):
        return {k: _strip_default(v) for k, v in obj.items() if k != "default"}
    if isinstance(obj, list):
        return [_strip_default(x) for x in obj]
    return obj


# ─────────────────────────── build_function_tools ─────────────────────────── #
def build_function_tools(
    *,
    use_tools: Iterable[str] | None = None,
    exclude_tools: Iterable[str] | None = None,
) -> List[Callable]:
    """
    FastMCP 登録ツールから OpenAI Agents SDK 用の FunctionTool を生成するユーティリティ。

    Parameters
    ----------
    use_tools : Iterable[str] | None, optional
        利用したいツール名を列挙。None の場合は全ツールが対象になる。
    exclude_tools : Iterable[str] | None, optional
        除外したいツール名を列挙。None の場合は除外なし。

    Both ``use_tools`` and ``exclude_tools`` を同時に指定した場合は、

    1. ``use_tools`` でホワイトリストを作成
    2. その後 ``exclude_tools`` でブラックリストを適用

    という手順でフィルタリングされます。
    """
    # ───── ① FastMCP 側のツール一覧取得 ─────
    tools_dict: Dict[str, Callable] = get_tools()
    if not tools_dict:
        raise RuntimeError("No FastMCP tools available in current context")

    selected: Dict[str, Callable]

    # ▶️ 変更点 ───────────────
    #  ホワイトリスト（use_tools）→ ブラックリスト（exclude_tools）の順で適用
    #  両方 None の場合は全ツール
    #  ───────────────────────
    if use_tools:
        selected = {n: tools_dict[n] for n in use_tools if n in tools_dict}
    else:
        selected = dict(tools_dict)  # 全ツールを複製

    if exclude_tools:
        for n in exclude_tools:
            selected.pop(n, None)  # 存在しない場合は無視

    if not selected:
        raise ValueError("フィルタリングの結果、使用可能なツールが 0 件になりました")

    # ───── ② OpenAI FunctionTool 化 ─────
    ft = _ensure_function_tool()
    oa_tools: List[Callable] = []

    for tname, call_fn in selected.items():
        async_fn = _as_async(call_fn)
        validated_fn = _wrap_with_pydantic(async_fn)
        tool_obj = ft(
            name_override=tname,
            description_override=(validated_fn.__doc__ or tname),
            strict_mode=False,
        )(validated_fn)

        # -- JSON-Schema 後処理 ---------------------------------------- #
        schema = _strip_default(tool_obj.params_json_schema)

        # required = properties の全キー（OpenAI 仕様）
        props = schema.get("properties", {})
        schema["required"] = list(props.keys()) if props else []

        tool_obj.params_json_schema = schema
        oa_tools.append(tool_obj)

    return oa_tools