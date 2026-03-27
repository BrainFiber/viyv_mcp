# decorators.py
# Decorators for MCP tool/resource/prompt/entry registration
import functools, inspect, logging
from typing import (
    Any, Callable, Union,
    get_type_hints,
)

from pydantic import create_model

from viyv_mcp.server import McpServer
from viyv_mcp.server.registry import ResourceEntry, PromptEntry
from viyv_mcp.app.entry_registry import add_entry

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# 内部ユーティリティ                                                          #
# --------------------------------------------------------------------------- #
def _get_mcp_from_stack() -> McpServer:
    """call-stack から McpServer インスタンスを探す。"""
    for frame in inspect.stack():
        loc = frame.frame.f_locals
        mcp_obj = loc.get("mcp")
        if isinstance(mcp_obj, McpServer):
            return mcp_obj

        self_obj = loc.get("self")
        if (
            self_obj is not None
            and hasattr(self_obj, "_mcp")
            and isinstance(getattr(self_obj, "_mcp"), McpServer)
        ):
            return getattr(self_obj, "_mcp")

    raise RuntimeError("McpServer instance not found in call-stack")


def _ensure_async(fn: Callable) -> Callable:
    """Wrap a sync function in an async wrapper if needed."""
    if inspect.iscoroutinefunction(fn):
        return fn

    @functools.wraps(fn)
    async def _wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return _wrapper


def _build_input_schema(fn: Callable) -> dict:
    """Generate JSON Schema from a function's type hints using pydantic."""
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception:
        hints = {}
    fields: dict = {}
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        ann = hints.get(pname, Any)
        if param.default is inspect.Parameter.empty:
            fields[pname] = (ann, ...)
        else:
            fields[pname] = (ann, param.default)
    if not fields:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    try:
        model = create_model(f"{fn.__name__}_Input", **fields)
        schema = model.model_json_schema()
    except Exception:
        props = {pname: {"type": "string"} for pname in fields}
        required = [p for p, v in fields.items() if v[1] is ...]
        return {"type": "object", "properties": props, "required": required}
    schema.pop("title", None)
    schema.setdefault("type", "object")
    schema.setdefault("additionalProperties", False)
    return schema


# --------------------------------------------------------------------------- #
# @tool デコレータ                                                             #
# --------------------------------------------------------------------------- #
def tool(
    name: str | None = None,
    description: str | None = None,
    tags: set[str] | None = None,
    group: str | None = None,
    title: str | None = None,
    destructive: bool | None = None,
    namespace: str | None = None,
    security_level: int | None = None,
):
    """ツールを McpServer に登録するデコレータ。"""

    def decorator(fn: Callable[..., Any]):
        mcp = _get_mcp_from_stack()
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or f"Viyv tool '{tool_name}'")

        impl = _ensure_async(fn)
        input_schema = _build_input_schema(fn)

        try:
            mcp.register_tool(
                name=tool_name,
                description=tool_desc,
                fn=impl,
                input_schema=input_schema,
                tags=tags,
                group=group,
                title=title,
                destructive=destructive,
                namespace=namespace,
                security_level=security_level,
            )
        except Exception as e:
            logger.error(f"Failed to register tool '{tool_name}': {e}")
            return fn

        return fn

    return decorator


# --------------------------------------------------------------------------- #
# @resource デコレータ                                                         #
# --------------------------------------------------------------------------- #
def resource(
    uri: str,
    name: str | None = None,
    description: str | None = None,
    mime_type: str | None = None,
):
    def decorator(fn: Callable):
        mcp = _get_mcp_from_stack()
        mcp.registry.register_resource(ResourceEntry(
            uri=uri,
            name=name or fn.__name__,
            description=description or fn.__doc__ or "",
            fn=fn,
            mime_type=mime_type,
        ))
        return fn
    return decorator


# --------------------------------------------------------------------------- #
# @prompt デコレータ                                                           #
# --------------------------------------------------------------------------- #
def prompt(name: str | None = None, description: str | None = None):
    def decorator(fn: Callable):
        mcp = _get_mcp_from_stack()
        mcp.registry.register_prompt(PromptEntry(
            name=name or fn.__name__,
            description=description or fn.__doc__ or "",
            fn=fn,
        ))
        return fn
    return decorator


# --------------------------------------------------------------------------- #
# @entry デコレータ                                                            #
# --------------------------------------------------------------------------- #
def entry(path: str):
    """ASGI アプリまたはファクトリ関数を指定パスにマウントする。"""

    def decorator(target: Union[Callable, Any]):
        add_entry(path, target)
        return target

    return decorator
