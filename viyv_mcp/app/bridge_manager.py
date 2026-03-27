# File: app/bridge_manager.py

import asyncio
import os
import json
import glob
import logging
import pathlib
from contextlib import AsyncExitStack
from typing import List, Tuple, Set

from mcp import ClientSession, types
from mcp.client.stdio import stdio_client, StdioServerParameters
from fastmcp import FastMCP
import inspect

# タイムアウト定数
BRIDGE_STARTUP_TIMEOUT = 30   # seconds: 外部 MCP サーバー起動 + initialize の上限
BRIDGE_SHUTDOWN_TIMEOUT = 10  # seconds: シャットダウンの上限

# 内部型
BridgeHandle = Tuple[str, AsyncExitStack, ClientSession]

logger = logging.getLogger(__name__)


def _make_tool(name: str, desc: str, input_schema, output_schema=None) -> types.Tool:
    """types.Tool コンストラクタの互換レイヤ（MCP SDK バージョン差異を吸収）"""
    try:
        return types.Tool(
            name=name, description=desc,
            inputSchema=input_schema, outputSchema=output_schema,
        )
    except TypeError:
        return types.Tool(name=name, description=desc, inputSchema=input_schema)

# ---------------------------------------------------------------------------
# Resource モデルのフィールドを動的に確認して互換レイヤを作る
# ---------------------------------------------------------------------------
# Pydantic V2では__fields__がmodel_fieldsに変更された
_RESOURCE_FIELDS = set(getattr(types.Resource, 'model_fields', types.Resource.__dict__).keys())
_RESOURCE_USES_URI_TEMPLATE = "uriTemplate" in _RESOURCE_FIELDS          # 旧仕様
_RESOURCE_USES_URI = "uri" in _RESOURCE_FIELDS                           # 新仕様
_RESOURCE_USES_NAME = "name" in _RESOURCE_FIELDS

def _build_resource(uri_value: str, desc: str = "", name: str | None = None) -> types.Resource:
    """
    SDK のバージョン差異を吸収して Resource インスタンスを生成
    """
    kwargs: dict = {"description": desc}
    if _RESOURCE_USES_URI_TEMPLATE:
        kwargs["uriTemplate"] = uri_value
    elif _RESOURCE_USES_URI:
        kwargs["uri"] = uri_value
    if _RESOURCE_USES_NAME:
        kwargs["name"] = name or uri_value
    return types.Resource(**kwargs)

def _get_resource_uri(resource: types.Resource) -> str:
    """
    Resource インスタンスから URI を取得（SDK バージョン互換）
    新仕様では 'uri'、旧仕様では 'uriTemplate' を使用
    """
    if hasattr(resource, 'uri'):
        return resource.uri
    elif hasattr(resource, 'uriTemplate'):
        return resource.uriTemplate
    else:
        # フォールバック: 属性が見つからない場合
        return "unknown://resource"

async def init_bridges(
    mcp: FastMCP,
    config: str,
) -> List[BridgeHandle]:
    """
    外部 MCP サーバー(stdio)を起動して tools/resources/prompts を動的登録。

    Parameters
    ----------
    config : str
        ディレクトリパス (*.json をスキャン) または単一 JSON ファイルパス。
    """
    bridges: List[BridgeHandle] = []

    if os.path.isfile(config):
        cfg_files = [config]
    else:
        cfg_files = glob.glob(os.path.join(config, "*.json"))

    for cfg_file in cfg_files:
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {cfg_file}: {e}")
            continue

        name         = cfg.get("name", "external")
        cmd          = cfg["command"]
        args         = cfg.get("args", [])
        cfg_tags: Set[str] = set(cfg.get("tags", []))
        cfg_group: str | None = cfg.get("group", None)
        cfg_group_map: dict[str, str] = cfg.get("group_map", {})
        json_env     = cfg.get("env", {})
        cwd          = cfg.get("cwd", None)
        # Security metadata
        cfg_namespace: str | None = cfg.get("namespace", None)
        raw_sl = cfg.get("security_level")
        if raw_sl is not None:
            try:
                cfg_security_level: int | None = int(raw_sl)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid security_level '{raw_sl}' in bridge config '{name}', "
                    "treating as unrestricted"
                )
                cfg_security_level = None
        else:
            cfg_security_level = None
        cfg_namespace_map: dict[str, str] = cfg.get("namespace_map", {})
        raw_sl_map = cfg.get("security_level_map", {})
        cfg_security_level_map: dict[str, int] = {}
        for sl_key, sl_val in raw_sl_map.items():
            try:
                cfg_security_level_map[sl_key] = int(sl_val)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid security_level_map value '{sl_val}' for tool '{sl_key}', skipping"
                )

        # 環境変数マージ（OS が優先）
        env_merged = {k: os.environ.get(k, v) for k, v in json_env.items()}

        # cwdが指定されていて存在しない場合は作成
        if cwd:
            cwd_path = pathlib.Path(cwd)
            if not cwd_path.exists():
                logger.info(f"Creating working directory: {cwd}")
                cwd_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"=== Starting external MCP server '{name}' ===")

        server_params = StdioServerParameters(command=cmd, args=args, env=env_merged or None, cwd=cwd)

        # --- プロセス / セッション確立 (AsyncExitStack + タイムアウト) -------
        exit_stack = AsyncExitStack()
        try:
            async def _start_bridge():
                read_stream, write_stream = await exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                session = await exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                return session

            session = await asyncio.wait_for(
                _start_bridge(), timeout=BRIDGE_STARTUP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{name}] Startup timed out after {BRIDGE_STARTUP_TIMEOUT}s, skipping"
            )
            await exit_stack.aclose()
            continue
        except Exception as e:
            logger.error(f"[{name}] Startup failed: {e}, cleaning up")
            await exit_stack.aclose()
            continue

        logger.info(f"[{name}] MCP initialize() done")

        # ----------------------- Tools ----------------------------------------------
        tools = await _safe_list_tools(session, server_name=name)
        for t in tools:
            tool_group = cfg_group_map.get(t.name, cfg_group)
            tool_ns = cfg_namespace_map.get(t.name, cfg_namespace)
            tool_sl = cfg_security_level_map.get(t.name, cfg_security_level)
            _register_tool_bridge(mcp, session, t, cfg_tags, tool_group, tool_ns, tool_sl)
        logger.info(f"[{name}] Tools => {[x.name for x in tools]}")

        # ----------------------- Resources ------------------------------------------
        resources = await _safe_list_resources(session, server_name=name)
        for r in resources:
            _register_resource_bridge(mcp, session, r)
        if resources:
            logger.info(f"[{name}] Resources => {[_get_resource_uri(r) for r in resources]}")

        # ----------------------- Prompts --------------------------------------------
        prompts = await _safe_list_prompts(session, server_name=name)
        for p in prompts:
            _register_prompt_bridge(mcp, session, p)
        if prompts:
            logger.info(f"[{name}] Prompts => {[p.name for p in prompts]}")

        bridges.append((name, exit_stack, session))

    return bridges


async def close_bridges(bridges: List[BridgeHandle]):
    """
    init_bridges() で起動したサブプロセス/セッションを全て終了。
    AsyncExitStack.aclose() が session → stdio の順にクリーンアップする。
    """
    for (name, exit_stack, session) in bridges:
        logger.info(f"=== Shutting down external MCP server '{name}' ===")
        try:
            await asyncio.wait_for(
                exit_stack.aclose(), timeout=BRIDGE_SHUTDOWN_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{name}] Shutdown timed out after {BRIDGE_SHUTDOWN_TIMEOUT}s"
            )
        except Exception as e:
            logger.error(f"[{name}] Shutdown error: {e}")


# ----------------------------------------------------------------------------
# 安全ラッパ: Tools
# ----------------------------------------------------------------------------
async def _safe_list_tools(session: ClientSession, server_name: str) -> List[types.Tool]:
    """
    list_tools() を呼び出し、取得データを  types.Tool に変換して返す。
    外部サーバーがタプル等を返す場合、inputSchema/outputSchemaなどを補完。
    未実装(メソッドが無い)の場合は空リストを返す。
    """
    try:
        raw_tools = await session.list_tools()  # 失敗するとException
    except Exception as e:
        logger.warning(f"[{server_name}] list_tools error => {e}")
        return []

    tools_converted = []
    # raw_tools が ListToolsResultの場合、.tools でツール配列を取得
    for item in raw_tools.tools:
        if isinstance(item, types.Tool):
            # すでに正しい型。バリデーション対策で空のinputSchema/outputSchema埋めるのも可
            tools_converted.append(item)

        elif isinstance(item, dict):
            # 例: {"name": "...", "description": "..."}
            name = item.get("name", "unknown_tool")
            desc = item.get("description", "")
            input_schema = item.get("inputSchema", [])
            output_schema = item.get("outputSchema", [])
            tool_obj = _make_tool(name, desc, input_schema, output_schema)
            tools_converted.append(tool_obj)

        elif isinstance(item, tuple):
            # 例: ("tool_name", "desc", ...)
            tool_name = str(item[0]) if len(item) > 0 else "unknown_tool"
            desc = str(item[1]) if len(item) > 1 else ""
            tool_obj = _make_tool(tool_name, desc, {})
            tools_converted.append(tool_obj)
        else:
            # 不明な形式の場合、最低限の情報だけ使う
            logger.warning(f"[{server_name}] Unexpected tool format: {item}")
            tool_obj = _make_tool(
                f"unknown_{len(tools_converted)+1}", str(item), {},
            )
            tools_converted.append(tool_obj)

    return tools_converted


# ----------------------------------------------------------------------------
# 安全ラッパ: Resources
# ----------------------------------------------------------------------------
async def _safe_list_resources(session: ClientSession, server_name: str) -> List[types.Resource]:
    """
    list_resources() を呼び出し、types.Resource に変換して返す。
    SDK のバージョン差異を透過的に処理する。

    MCP Protocol 仕様:
    - list_resources() は ListResourcesResult を返す
    - ListResourcesResult: {resources: [...], meta: {...}, nextCursor: "..."}
    - 実際のリソース配列は .resources 属性にある
    """
    try:
        raw_resources = await session.list_resources()
    except Exception as e:
        logger.warning(f"[{server_name}] list_resources error => {e}")
        return []

    # MCP Protocol: ListResourcesResult.resources を取得
    resources_list = getattr(raw_resources, 'resources', [])

    resources_converted: List[types.Resource] = []
    for item in resources_list:
        try:
            if isinstance(item, types.Resource):
                # すでに正しい型
                resources_converted.append(item)

            elif isinstance(item, dict):
                uri_val = item.get("uriTemplate") or item.get("uri") or "unknown://{id}"
                desc = item.get("description", "")
                name = item.get("name")
                resources_converted.append(_build_resource(uri_val, desc, name))

            elif isinstance(item, tuple):
                uri_val = str(item[0]) if len(item) > 0 else "unknown://{id}"
                desc = str(item[1]) if len(item) > 1 else ""
                resources_converted.append(_build_resource(uri_val, desc))

            else:
                logger.warning(f"[{server_name}] Unexpected resource format: {item}")
                resources_converted.append(_build_resource(f"unknown://{len(resources_converted)+1}", str(item)))
        except Exception as e:
            logger.warning(f"[{server_name}] Resource convert error => {e} (raw={item})")

    # ページネーション情報のログ出力
    next_cursor = getattr(raw_resources, 'nextCursor', None)
    if next_cursor:
        logger.info(f"[{server_name}] Resources have more pages (nextCursor: {next_cursor[:50]}...)")

    return resources_converted

# ----------------------------------------------------------------------------
# 安全ラッパ: Prompts
# ----------------------------------------------------------------------------
async def _safe_list_prompts(session: ClientSession, server_name: str) -> List[types.Prompt]:
    """
    list_prompts() を呼び出し、types.Prompt に変換して返す。
    Method not found等で失敗したら空リスト。

    MCP Protocol 仕様:
    - list_prompts() は ListPromptsResult を返す
    - ListPromptsResult: {prompts: [...], meta: {...}, nextCursor: "..."}
    - 実際のプロンプト配列は .prompts 属性にある
    """
    try:
        raw_prompts = await session.list_prompts()
    except Exception as e:
        logger.warning(f"[{server_name}] list_prompts error => {e}")
        return []

    # MCP Protocol: ListPromptsResult.prompts を取得
    prompts_list = getattr(raw_prompts, 'prompts', [])

    prompts_converted = []
    for item in prompts_list:
        if isinstance(item, types.Prompt):
            prompts_converted.append(item)

        elif isinstance(item, dict):
            pname = item.get("name", "unknown_prompt")
            desc = item.get("description", "")
            args = item.get("arguments", [])
            p = types.Prompt(
                name=pname,
                description=desc,
                arguments=args,
            )
            prompts_converted.append(p)
        elif isinstance(item, tuple):
            pname = str(item[0]) if len(item) > 0 else "unknown_prompt"
            desc = str(item[1]) if len(item) > 1 else ""
            p = types.Prompt(
                name=pname,
                description=desc,
                arguments=[],
            )
            prompts_converted.append(p)
        else:
            logger.warning(f"[{server_name}] Unexpected prompt format: {item}")
            p = types.Prompt(
                name=f"unknown_{len(prompts_converted)+1}",
                description=str(item),
                arguments=[],
            )
            prompts_converted.append(p)

    # ページネーション情報のログ出力
    next_cursor = getattr(raw_prompts, 'nextCursor', None)
    if next_cursor:
        logger.info(f"[{server_name}] Prompts have more pages (nextCursor: {next_cursor[:50]}...)")

    return prompts_converted


# ----------------------------------------------------------------------------
# 実際の登録 (tool / resource / prompt)
# ----------------------------------------------------------------------------
def _register_tool_bridge(
    mcp: FastMCP,
    session: ClientSession,
    tool_info: types.Tool,
    cfg_tags: Set[str] | None = None,
    cfg_group: str | None = None,
    cfg_namespace: str | None = None,
    cfg_security_level: int | None = None,
):
    """
    tool_info から inputSchema を解析し、kwargs を定義して bridged_tool を登録する

    JSON Schema の情報（型、default、required、description）を pydantic の Field と
    typing.Annotated を用いて __signature__ に動的に組み上げるように改修済み。
    """
    tool_name = tool_info.name
    desc = tool_info.description or f"Bridged external tool '{tool_name}'"
    input_schema = tool_info.inputSchema or {}

    params = []
    # JSON Schema の properties, required を利用して関数パラメータを構築
    if isinstance(input_schema, dict):
        props = input_schema.get("properties", {})
        required_fields = input_schema.get("required", [])
        json_type_mapping = {
            'string': str,
            'integer': int,
            'object': dict,
            'boolean': bool,
            'number': float,
            'array': list
        }
        from typing import Annotated, Optional
        from pydantic import Field

        for name, schema in props.items():
            json_type = schema.get("type", "any")
            base_type = json_type_mapping.get(json_type, object)
            description_field = schema.get("description", "")
            # 必須なら default は省略（pydanticでは ... を指定する）
            if name in required_fields:
                default_val = inspect.Parameter.empty
                field_default = ...  # required
            else:
                # default が指定されていなければ None をデフォルトにし、Optional にする
                if "default" in schema:
                    default_val = schema["default"]
                    field_default = default_val
                else:
                    default_val = None
                    field_default = None
                    base_type = Optional[base_type]
            # Annotated に Field の情報を付与
            annotated_type = Annotated[base_type, Field(field_default, description=description_field)]
            param = inspect.Parameter(
                name,
                kind=inspect.Parameter.KEYWORD_ONLY, 
                default=(default_val if default_val is not inspect.Parameter.empty else inspect.Parameter.empty),
                annotation=annotated_type
            )
            params.append(param)
    else:
        # input_schema が dict でなければ、従来の挙動にフォールバック
        arg_names = []
        props = {}
        if isinstance(input_schema, dict):
            props = input_schema.get("properties", {})
            arg_names = list(props.keys())
        for name in arg_names:
            param = inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty
            )
            params.append(param)

    async def _impl(**all_kwargs):
        # 必要な引数だけ抽出し、値がNone/空でないものだけ渡す
        args_for_tool = {k: v for k, v in all_kwargs.items() if k in [p.name for p in params] and v is not None}
        return await session.call_tool(tool_name, arguments=args_for_tool)

    bridged_tool = _impl
    bridged_tool.__signature__ = inspect.Signature(params)

    # ★ __annotations__ を補完して型ヒント解決エラーを防ぐ
    from typing import Any
    bridged_tool.__annotations__ = {
        p.name: (p.annotation if p.annotation is not inspect._empty else Any)
        for p in params
    }
    bridged_tool.__annotations__["return"] = Any

    bridged_tool.__doc__ = desc

    # ── メタデータ構築 (group のみ _meta に含める) ──
    meta_data = None
    if cfg_group:
        meta_data = {"viyv": {"group": cfg_group}}

    # FastMCP にツールを登録
    mcp.tool(
        name=tool_name,
        description=desc,
        tags=cfg_tags,
        meta=meta_data,
    )(bridged_tool)

    # セキュリティイベント通知
    from viyv_mcp.decorators import _fire_tool_event
    _fire_tool_event("registered", tool_name, {
        "namespace": cfg_namespace,
        "security_level": cfg_security_level,
    })


def _register_resource_bridge(mcp: FastMCP, session: ClientSession, rinfo: types.Resource):
    # SDK バージョン互換: uri または uriTemplate を取得
    uri_template = _get_resource_uri(rinfo)
    desc = rinfo.description or f"Bridged external resource '{uri_template}'"

    @mcp.resource(uri_template)
    async def bridged_resource(**kwargs):
        from string import Template
        t = Template(uri_template.replace("{", "${"))
        actual_uri = t.substitute(**kwargs)

        content, mime_type = await session.read_resource(actual_uri)
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return content

    bridged_resource.__doc__ = desc


def _register_prompt_bridge(mcp: FastMCP, session: ClientSession, pinfo: types.Prompt):
    prompt_name = pinfo.name
    desc = pinfo.description or f"Bridged external prompt '{prompt_name}'"

    # ------------------------------------------------------------
    # 1) Prompt 引数をシグネチャ化  (keyword-only が必須)
    # ------------------------------------------------------------
    params: list[inspect.Parameter] = []
    annos: dict[str, type] = {}

    # MCP Protocol: pinfo.arguments は list[PromptArgument] (Pydantic BaseModel)
    # PromptArgument: name: str, description: str | None, required: bool | None
    # Note: MCP Protocol には型情報がないため、すべて str として扱う
    for arg in (pinfo.arguments or []):
        # PromptArgument オブジェクトから属性を取得
        name = arg.name
        arg_required = arg.required if arg.required is not None else True  # デフォルトは True

        # MCP Protocol には type 情報がないため、すべて str として扱う
        py_type = str

        # required が False の場合は default=None を設定
        default = inspect.Parameter.empty if arg_required else None

        param = inspect.Parameter(
            name=name,
            kind=inspect.Parameter.KEYWORD_ONLY,      # FastMCP 2.3 requirement
            default=default,
            annotation=py_type,
        )
        params.append(param)
        annos[name] = py_type

    # ------------------------------------------------------------
    # 2) 本体実装
    # ------------------------------------------------------------
    async def _impl(**kwargs):
        result = await session.get_prompt(
            prompt_name,
            arguments={k: str(v) for k, v in kwargs.items()},
        )
        return result.messages

    _impl.__doc__ = desc
    _impl.__signature__ = inspect.Signature(params)
    _impl.__annotations__ = annos | {"return": list}     # 型ヒントを補完

    # ------------------------------------------------------------
    # 3) 登録
    # ------------------------------------------------------------
    mcp.prompt(name=prompt_name, description=desc)(_impl)


# ----------------------------------------------------------------------------
# WSブリッジ向け: ツール動的削除ヘルパー
# ----------------------------------------------------------------------------
def unregister_bridged_tools(mcp: FastMCP, tool_names: List[str]) -> None:
    """ブリッジツールを動的に削除する（WSブリッジ切断時用）"""
    from viyv_mcp.decorators import _unregister_tool_fn

    for name in tool_names:
        try:
            if hasattr(mcp, "remove_tool"):
                mcp.remove_tool(name)
            _unregister_tool_fn(name)  # also fires "unregistered" event
        except Exception as e:
            logger.warning(f"Failed to remove tool '{name}': {e}")