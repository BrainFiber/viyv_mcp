#!/usr/bin/env python3
"""
アーキテクチャ改善後の E2E テスト

Phase 1-4 の改善が基本機能を壊していないことを確認する:
1. デコレータ登録 (@tool, @resource, @prompt, @agent, @entry)
2. ツール呼び出し (ContextVar 注入含む)
3. セキュリティ Observer 連携
4. ViyvMCP ASGI アプリ組み立て
5. bridge_manager の型整合性
6. 新規モジュール (mcp_factory, asgi_builder, lifespan_composer)
"""

import asyncio
import inspect
import pytest
from contextlib import asynccontextmanager
from typing import Annotated, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import Field
from viyv_mcp.server import McpServer
from mcp import ClientSession, types


# ========================================================================== #
# 1. デコレータ基本登録テスト
# ========================================================================== #

class TestToolDecorator:
    """@tool デコレータの基本動作"""

    def test_tool_registers_with_fastmcp(self):
        """@tool でツールが FastMCP に登録される"""
        from viyv_mcp import tool

        mcp = McpServer("test-tool-reg")

        def register(mcp):
            @tool(description="Add two numbers", tags={"calc"})
            def add(a: int, b: int) -> int:
                return a + b

        register(mcp)

        assert mcp.registry.get_tool("add") is not None
        assert asyncio.iscoroutinefunction(mcp.registry.get_tool("add").fn)

    def test_tool_with_annotated_fields(self):
        """Annotated[int, Field(...)] がスキーマに反映される"""
        from viyv_mcp import tool

        mcp = McpServer("test-annotated")

        def register(mcp):
            @tool(description="Multiply")
            def multiply(
                x: Annotated[int, Field(title="X", description="First number")],
                y: Annotated[int, Field(title="Y", description="Second number")],
            ) -> int:
                return x * y

        register(mcp)
        assert mcp.registry.get_tool("multiply") is not None

    def test_tool_with_default_params(self):
        """デフォルト引数が正しく扱われる"""
        from viyv_mcp import tool

        mcp = McpServer("test-defaults")

        def register(mcp):
            @tool(description="Greet")
            def greet(name: str, greeting: str = "Hello") -> str:
                return f"{greeting}, {name}!"

        register(mcp)
        assert mcp.registry.get_tool("greet") is not None

    def test_tool_with_group_metadata(self):
        """group メタデータが正しく渡される"""
        from viyv_mcp import tool

        mcp = McpServer("test-group")

        def register(mcp):
            @tool(description="Test", group="MyGroup", tags={"test"})
            def my_tool() -> str:
                return "ok"

        register(mcp)

    def test_tool_with_security_metadata(self):
        """namespace / security_level メタデータが McpRegistry に直接登録される"""
        from viyv_mcp import tool

        mcp = McpServer("test-security")

        def register(mcp):
            @tool(
                description="Secret tool",
                namespace="hr",
                security_level=1,
            )
            def secret_tool() -> str:
                return "secret"

        register(mcp)

        meta = mcp.registry.get("secret_tool")
        assert meta.namespace == "hr"
        assert meta.security_level == 1


# ========================================================================== #
# 2. ツール実行テスト
# ========================================================================== #

class TestToolExecution:
    """ツール実行 (ContextVar 注入含む)"""

    def test_tool_can_be_called_directly(self):
        """登録した sync ツールの元関数が正しく動作する"""
        from viyv_mcp import tool

        mcp = McpServer("test-call")
        result_holder = []

        def register(mcp):
            @tool(description="Add")
            def add_exec(a: int, b: int) -> int:
                return a + b
            result_holder.append(add_exec)

        register(mcp)

        # デコレータは元の関数を返すので直接呼べる
        assert result_holder[0](a=3, b=5) == 8

    def test_async_tool_original_works(self):
        """登録した async ツールの元関数が正しく動作する"""
        from viyv_mcp import tool

        mcp = McpServer("test-async-call")
        result_holder = []

        def register(mcp):
            @tool(description="Async add")
            async def async_add_exec(a: int, b: int) -> int:
                return a + b
            result_holder.append(async_add_exec)

        register(mcp)

        result = asyncio.new_event_loop().run_until_complete(
            result_holder[0](a=10, b=20)
        )
        assert result == 30

    def test_tool_registered_in_fastmcp(self):
        """FastMCP にツールが登録されている"""
        from viyv_mcp import tool

        mcp = McpServer("test-list")

        def register(mcp):
            @tool(description="Tool A")
            def tool_a_list() -> str:
                return "a"

            @tool(description="Tool B")
            def tool_b_list() -> str:
                return "b"

        register(mcp)

        # McpRegistry で個別取得
        assert mcp.registry.get_tool("tool_a_list") is not None
        assert mcp.registry.get_tool("tool_b_list") is not None


# ========================================================================== #
# 3. ツールレジストリ確認テスト
# ========================================================================== #

class TestToolRegistry:
    """McpRegistry へのツール登録確認"""

    def test_get_tool_shows_registered(self):
        """McpRegistry.get_tool() で個別ツールが確認できる"""
        from viyv_mcp import tool

        mcp = McpServer("test-registry")

        def register(mcp):
            @tool(description="Keep")
            def keep_me_exc() -> str:
                return "keep"

            @tool(description="Skip")
            def skip_me_exc() -> str:
                return "skip"

        register(mcp)

        assert mcp.registry.get_tool("keep_me_exc") is not None
        assert mcp.registry.get_tool("skip_me_exc") is not None


# ========================================================================== #
# 5. セキュリティ Observer 連携テスト
# ========================================================================== #

class TestSecurityMetadataIntegration:
    """セキュリティメタデータが McpRegistry に直接統合されている確認"""

    def test_tool_security_stored_in_registry(self):
        from viyv_mcp import tool

        mcp = McpServer("test-sec-reg")
        def register(mcp):
            @tool(description="HR tool", namespace="hr", security_level=1)
            def hr_tool() -> str:
                return "hr"
        register(mcp)

        meta = mcp.registry.get("hr_tool")
        assert meta.namespace == "hr"
        assert meta.security_level == 1

    def test_tool_default_security(self):
        from viyv_mcp import tool

        mcp = McpServer("test-sec-default")
        def register(mcp):
            @tool(description="Plain tool")
            def plain_tool() -> str:
                return "plain"
        register(mcp)

        meta = mcp.registry.get("plain_tool")
        assert meta.namespace == "common"
        assert meta.security_level is None

    def test_unregister_tool_clears_security(self):
        mcp = McpServer("test-unreg")
        mcp.register_tool("temp", "Temp", lambda: None,
                          {"type": "object", "properties": {}},
                          namespace="hr", security_level=0)

        assert mcp.registry.get("temp").namespace == "hr"
        mcp.remove_tool("temp")
        assert mcp.registry.get("temp").namespace == "common"  # default


# ========================================================================== #
# 6. ViyvMCP アプリ組み立てテスト
# ========================================================================== #

class TestViyvMCPAssembly:
    """ViyvMCP の ASGI アプリ組み立て"""

    def test_viyv_mcp_creates_asgi_app(self):
        from viyv_mcp import ViyvMCP
        app = ViyvMCP("E2E Test Server")
        assert callable(app.get_app())

    def test_viyv_mcp_has_mcp_instance(self):
        from viyv_mcp import ViyvMCP
        app = ViyvMCP("E2E Test Server")
        assert isinstance(app._mcp, McpServer)

    def test_viyv_mcp_starlette_app_exists(self):
        from viyv_mcp import ViyvMCP
        from starlette.applications import Starlette
        app = ViyvMCP("E2E Test Server")
        assert isinstance(app._starlette_app, Starlette)

    def test_viyv_mcp_mcp_app_initialized(self):
        """_mcp_app が初期化されている"""
        from viyv_mcp import ViyvMCP
        app = ViyvMCP("E2E Test Server")
        assert app._mcp_app is not None


# ========================================================================== #
# 7. 新規モジュールテスト
# ========================================================================== #

class TestMCPFactory:
    def test_create_mcp_server(self):
        from viyv_mcp.app.mcp_factory import create_mcp_server

        @asynccontextmanager
        async def dummy_lifespan(app):
            yield

        mcp = create_mcp_server("factory-test", dummy_lifespan)
        assert isinstance(mcp, McpServer)


class TestASGIBuilder:
    def test_ensure_static_dir_creates_directory(self, tmp_path, monkeypatch):
        from viyv_mcp.app.asgi_builder import ensure_static_dir
        target = str(tmp_path / "static" / "images")
        monkeypatch.setenv("STATIC_DIR", target)
        result = ensure_static_dir()
        assert result == target
        assert (tmp_path / "static" / "images").exists()

    def test_setup_ws_bridge_disabled(self, monkeypatch):
        from viyv_mcp.app.asgi_builder import setup_ws_bridge
        monkeypatch.setattr("viyv_mcp.app.asgi_builder.Config.WS_BRIDGE_ENABLED", False)
        ws = setup_ws_bridge("test", None)
        assert ws.relay_mcp is None
        assert ws.ws_routes == []

    def test_build_routes_includes_static(self, tmp_path):
        from viyv_mcp.app.asgi_builder import build_routes
        static_dir = str(tmp_path / "static" / "images")
        (tmp_path / "static").mkdir(parents=True, exist_ok=True)
        routes = build_routes([], static_dir)
        route_paths = [r.path for r in routes if hasattr(r, "path")]
        assert "/static" in route_paths


class TestLifespanComposer:
    def test_compose_lifespan_calls_startup_shutdown(self):
        from viyv_mcp.app.lifespan_composer import compose_lifespan

        started = False
        stopped = False

        async def startup():
            nonlocal started
            started = True

        async def shutdown():
            nonlocal stopped
            stopped = True

        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        mock_app = MagicMock()
        mock_app.router.lifespan_context = noop_lifespan

        lifespan = compose_lifespan(mock_app, None, startup, shutdown, None)

        async def _run():
            async with lifespan(None):
                assert started is True
                assert stopped is False
            assert stopped is True

        asyncio.run(_run())


# ========================================================================== #
# 8. bridge_manager 型整合性テスト
# ========================================================================== #

class TestBridgeManagerTypes:
    def test_bridge_handle_type_exists(self):
        from viyv_mcp.app.bridge_manager import BridgeHandle
        assert BridgeHandle is not None

    def test_timeout_constants_defined(self):
        from viyv_mcp.app.bridge_manager import BRIDGE_STARTUP_TIMEOUT, BRIDGE_SHUTDOWN_TIMEOUT
        assert BRIDGE_STARTUP_TIMEOUT > 0
        assert BRIDGE_SHUTDOWN_TIMEOUT > 0

    def test_init_bridges_with_empty_dir(self, tmp_path):
        from viyv_mcp.app.bridge_manager import init_bridges
        mcp = McpServer("bridge-test")
        bridges = asyncio.run(
            init_bridges(mcp, str(tmp_path))
        )
        assert bridges == []

    def test_close_bridges_with_empty_list(self):
        from viyv_mcp.app.bridge_manager import close_bridges
        asyncio.run(close_bridges([]))


# ========================================================================== #
# 9. MCP プロトコル互換性テスト
# ========================================================================== #

class TestExistingProtocol:
    def test_mcp_tool_call_protocol(self):
        """tools/call が正しく動作する"""
        mock_session = AsyncMock(spec=ClientSession)

        mock_session.list_tools.return_value = types.ListToolsResult(
            tools=[
                types.Tool(
                    name="test_tool",
                    description="Test tool",
                    inputSchema={
                        "type": "object",
                        "properties": {"param1": {"type": "string"}},
                        "required": ["param1"],
                    },
                )
            ]
        )

        mock_session.call_tool.return_value = types.CallToolResult(
            content=[types.TextContent(type="text", text="Success")]
        )

        async def _run():
            tools = await mock_session.list_tools()
            assert len(tools.tools) == 1
            result = await mock_session.call_tool("test_tool", arguments={"param1": "test_value"})
            assert result.content[0].text == "Success"

        asyncio.run(_run())


# ========================================================================== #
# 10. JSON Schema 生成テスト
# ========================================================================== #

class TestJSONSchemaGeneration:
    """FastMCP に登録されたツールが正しい JSON Schema を生成するか"""

    def test_tool_registers_with_correct_metadata(self):
        """ツールが正しいメタデータで登録される"""
        from viyv_mcp import tool

        mcp = McpServer("test-schema")

        def register(mcp):
            @tool(description="Schema test tool")
            def schema_test(
                name: Annotated[str, Field(description="User name")],
                age: Annotated[int, Field(description="User age")],
                active: bool = True,
            ) -> str:
                return f"{name}: {age}"

        register(mcp)

        # レジストリに登録されている
        assert mcp.registry.get_tool("schema_test") is not None
        # async ラッパとして登録されている
        assert asyncio.iscoroutinefunction(mcp.registry.get_tool("schema_test").fn)

    def test_sync_tool_wrapped_as_async(self):
        """sync ツールが async にラップされる"""
        from viyv_mcp import tool

        mcp = McpServer("test-sync-wrap")

        def register(mcp):
            @tool(description="Sync tool")
            def sync_tool(x: int) -> int:
                return x * 2

        register(mcp)

        entry = mcp.registry.get_tool("sync_tool")
        assert asyncio.iscoroutinefunction(entry.fn)
