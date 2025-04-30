# File: app/bridge_manager.py

import os
import json
import glob
import logging
from typing import List, Tuple, Set

from mcp import ClientSession, types
from mcp.client.stdio import stdio_client, StdioServerParameters
from fastmcp import FastMCP
import inspect

logger = logging.getLogger(__name__)

async def init_bridges(
    mcp: FastMCP,
    config_dir: str,
) -> List[Tuple[str, "stdio_client", ClientSession]]:
    """
    config_dir/*.json を走査し、外部 MCP サーバー(stdio)を起動して
    list_tools / list_resources / list_prompts を取得し、FastMCP に動的登録。
    戻り値: [(server_name, stdio_ctx, session), ...]
    """
    bridges: List[Tuple[str, "stdio_client", ClientSession]] = []

    for cfg_file in glob.glob(os.path.join(config_dir, "*.json")):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {cfg_file}: {e}")
            continue

        name         = cfg.get("name", "external")
        cmd          = cfg["command"]
        args         = cfg.get("args", [])
        cfg_tags: Set[str] = set(cfg.get("tags", []))            # ★ 追加: config 由来タグ
        json_env     = cfg.get("env", {})

        # 環境変数マージ（OS が優先）
        env_merged = {k: os.environ.get(k, v) for k, v in json_env.items()}

        logger.info(f"=== Starting external MCP server '{name}' ===")

        server_params = StdioServerParameters(command=cmd, args=args, env=env_merged or None)

        # --- プロセス / セッション確立 ------------------------------------------------
        stdio_ctx = stdio_client(server_params)
        read_stream, write_stream = await stdio_ctx.__aenter__()

        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()
        logger.info(f"[{name}] MCP initialize() done")

        # ----------------------- Tools ----------------------------------------------
        tools = await _safe_list_tools(session, server_name=name)
        for t in tools:
            _register_tool_bridge(mcp, session, t, cfg_tags)     # ← タグを渡す
        logger.info(f"[{name}] Tools => {[x.name for x in tools]}")

        # ----------------------- Resources ------------------------------------------
        resources = await _safe_list_resources(session, server_name=name)
        for r in resources:
            _register_resource_bridge(mcp, session, r)
        if resources:
            logger.info(f"[{name}] Resources => {[r.uriTemplate for r in resources]}")

        # ----------------------- Prompts --------------------------------------------
        prompts = await _safe_list_prompts(session, server_name=name)
        for p in prompts:
            _register_prompt_bridge(mcp, session, p)
        if prompts:
            logger.info(f"[{name}] Prompts => {[p.name for p in prompts]}")

        bridges.append((name, stdio_ctx, session))

    return bridges


async def close_bridges(bridges: List[Tuple[str, "stdio_client", ClientSession]]):
    """
    init_bridges()で起動したサブプロセス/セッションを全て終了
    """
    for (name, stdio_ctx, session) in bridges:
        logger.info(f"=== Shutting down external MCP server '{name}' ===")
        # session.__aexit__
        try:
            await session.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"[{name}] session close error: {e}")

        # subprocess __aexit__
        try:
            await stdio_ctx.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"[{name}] process close error: {e}")


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
            tool_obj = types.Tool(
                name=name,
                description=desc,
                inputSchema=input_schema,
                outputSchema=output_schema,
            )
            tools_converted.append(tool_obj)

        elif isinstance(item, tuple):
            # 例: ("tool_name", "desc", ...)
            tool_name = str(item[0]) if len(item) > 0 else "unknown_tool"
            desc = str(item[1]) if len(item) > 1 else ""
            tool_obj = types.Tool(
                name=tool_name,
                description=desc,
                inputSchema=[],
                outputSchema=[],
            )
            tools_converted.append(tool_obj)
        else:
            # 不明な形式の場合、最低限の情報だけ使う
            logger.warning(f"[{server_name}] Unexpected tool format: {item}")
            tool_obj = types.Tool(
                name=f"unknown_{len(tools_converted)+1}",
                description=str(item),
                inputSchema=[],
                outputSchema=[],
            )
            tools_converted.append(tool_obj)

    return tools_converted


# ----------------------------------------------------------------------------
# 安全ラッパ: Resources
# ----------------------------------------------------------------------------
async def _safe_list_resources(session: ClientSession, server_name: str) -> List[types.Resource]:
    """
    list_resources() を呼び出し、types.Resource に変換して返す。
    Method not found等で失敗したら空リストを返す。
    """
    try:
        raw_resources = await session.list_resources()
    except Exception as e:
        logger.warning(f"[{server_name}] list_resources error => {e}")
        return []

    resources_converted = []
    for item in raw_resources:
        if isinstance(item, types.Resource):
            resources_converted.append(item)

        elif isinstance(item, dict):
            uri_template = item.get("uriTemplate", "unknown://{id}")
            desc = item.get("description", "")
            r = types.Resource(
                uriTemplate=uri_template,
                description=desc,
            )
            resources_converted.append(r)

        elif isinstance(item, tuple):
            # 例: ("slack://{channel}", "desc")
            uri_template = str(item[0]) if len(item) > 0 else "unknown://{id}"
            desc = str(item[1]) if len(item) > 1 else ""
            r = types.Resource(
                uriTemplate=uri_template,
                description=desc,
            )
            resources_converted.append(r)
        else:
            logger.warning(f"[{server_name}] Unexpected resource format: {item}")
            r = types.Resource(
                uriTemplate=f"unknown://{len(resources_converted)+1}",
                description=str(item),
            )
            resources_converted.append(r)

    return resources_converted

# ----------------------------------------------------------------------------
# 安全ラッパ: Prompts
# ----------------------------------------------------------------------------
async def _safe_list_prompts(session: ClientSession, server_name: str) -> List[types.Prompt]:
    """
    list_prompts() を呼び出し、types.Prompt に変換して返す。
    Method not found等で失敗したら空リスト。
    """
    try:
        raw_prompts = await session.list_prompts()
    except Exception as e:
        logger.warning(f"[{server_name}] list_prompts error => {e}")
        return []

    prompts_converted = []
    for item in raw_prompts:
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

    return prompts_converted


# ----------------------------------------------------------------------------
# 実際の登録 (tool / resource / prompt)
# ----------------------------------------------------------------------------
def _register_tool_bridge(mcp: FastMCP, session: ClientSession, tool_info: types.Tool, cfg_tags: Set[str] | None = None,):
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
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
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
    bridged_tool.__doc__ = desc

    mcp.add_tool(name=tool_name, fn=bridged_tool, description=desc, tags=cfg_tags)


def _register_resource_bridge(mcp: FastMCP, session: ClientSession, rinfo: types.Resource):
    uri_template = rinfo.uriTemplate
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

    @mcp.prompt(name=prompt_name)
    async def bridged_prompt(**kwargs):
        str_args = {k: str(v) for k, v in kwargs.items()}
        result = await session.get_prompt(prompt_name, arguments=str_args)
        return result.messages

    bridged_prompt.__doc__ = desc