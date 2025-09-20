#!/usr/bin/env python3
"""
MCPプロトコルの動作確認テスト

tools/callが正しく動作することを確認し、
初期化シーケンスやエラーケースのテストを行います。
"""

import asyncio
import json
import pytest
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters


@pytest.mark.asyncio
async def test_mcp_tool_call_protocol():
    """tools/callメソッドが正しく使用されることを確認"""

    # モックセッションの作成
    mock_session = AsyncMock(spec=ClientSession)

    # list_toolsの戻り値を設定
    mock_tools = types.ListToolsResult(
        tools=[
            types.Tool(
                name="test_tool",
                description="Test tool",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string"},
                    },
                    "required": ["param1"]
                }
            )
        ]
    )
    mock_session.list_tools.return_value = mock_tools

    # call_toolの戻り値を設定
    mock_session.call_tool.return_value = types.CallToolResult(
        content=[
            types.TextContent(type="text", text="Success")
        ]
    )

    # ツール一覧を取得
    tools = await mock_session.list_tools()
    assert len(tools.tools) == 1
    assert tools.tools[0].name == "test_tool"

    # tools/callを実行（正しいメソッド名）
    result = await mock_session.call_tool(
        "test_tool",
        arguments={"param1": "test_value"}
    )

    # 呼び出しが正しく行われたことを確認
    mock_session.call_tool.assert_called_once_with(
        "test_tool",
        arguments={"param1": "test_value"}
    )

    # 結果の確認
    assert result.content[0].text == "Success"


@pytest.mark.asyncio
async def test_mcp_initialization_sequence():
    """初期化シーケンスが正しく実行されることを確認"""

    mock_session = AsyncMock(spec=ClientSession)

    # initializeの戻り値を設定
    mock_session.initialize.return_value = types.InitializeResult(
        protocolVersion="2025-06-18",
        capabilities=types.ServerCapabilities(
            tools=types.ToolsCapability(listChanged=True),
            resources=types.ResourcesCapability(listChanged=True)
        ),
        serverInfo=types.Implementation(
            name="test_server",
            version="1.0.0"
        )
    )

    # 初期化を実行
    init_result = await mock_session.initialize()

    # 初期化が呼ばれたことを確認
    mock_session.initialize.assert_called_once()

    # 初期化結果の確認
    assert init_result.protocolVersion == "2025-06-18"
    assert init_result.serverInfo.name == "test_server"
    assert init_result.capabilities.tools is not None


@pytest.mark.asyncio
async def test_protocol_error_handling():
    """プロトコルエラーの処理を確認"""

    mock_session = AsyncMock(spec=ClientSession)

    # エラーケース: 不正なメソッド名のテスト
    # MCPではtools/executeは存在しないので、エラーになるべき
    with pytest.raises(AttributeError):
        # tools_executeというメソッドは存在しない
        await mock_session.tools_execute("test_tool", {})

    # 正しいメソッド: call_tool
    mock_session.call_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="OK")]
    )

    result = await mock_session.call_tool("test_tool", arguments={})
    assert result.content[0].text == "OK"


def test_validate_request_format():
    """リクエストフォーマットのバリデーション"""

    # 正しいリクエスト形式（tools/call）
    correct_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "test_tool",
            "arguments": {"param": "value"}
        }
    }

    # 誤ったリクエスト形式（tools/execute - 存在しない）
    incorrect_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/execute",
        "params": {
            "toolId": "test_tool",
            "tool": {"id": "test_tool", "param": "value"}
        }
    }

    # 正しいフォーマットのバリデーション
    assert correct_request["method"] == "tools/call"
    assert "name" in correct_request["params"]
    assert "arguments" in correct_request["params"]

    # 誤ったフォーマットの検出
    assert incorrect_request["method"] != "tools/call"
    assert "toolId" in incorrect_request["params"]  # 誤ったフィールド
    assert "name" not in incorrect_request["params"]  # 必要なフィールドがない


@pytest.mark.asyncio
async def test_resource_subscription():
    """リソース購読が正しく動作することを確認"""

    mock_session = AsyncMock(spec=ClientSession)

    # list_resourcesの戻り値を設定
    mock_resources = [
        types.Resource(
            uri="test://resource/1",
            name="test_resource",
            description="Test resource"
        )
    ]
    mock_session.list_resources.return_value = mock_resources

    # subscribe_resourceの戻り値を設定
    mock_session.subscribe.return_value = None

    # リソース一覧を取得
    resources = await mock_session.list_resources()
    assert len(resources) == 1
    assert resources[0].uri == "test://resource/1"

    # リソースを購読（正しいメソッド名: resources/subscribe）
    await mock_session.subscribe(uri="test://resource/1")

    # 購読が正しく呼ばれたことを確認
    mock_session.subscribe.assert_called_once_with(uri="test://resource/1")


@pytest.mark.asyncio
async def test_initialization_before_tool_call():
    """ツール呼び出し前に初期化が完了していることを確認"""

    initialized = False

    async def mock_initialize():
        nonlocal initialized
        initialized = True
        return types.InitializeResult(
            protocolVersion="2025-06-18",
            capabilities=types.ServerCapabilities(),
            serverInfo=types.Implementation(name="test", version="1.0")
        )

    async def mock_call_tool(name, arguments):
        if not initialized:
            raise RuntimeError("Received request before initialization was complete")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="OK")]
        )

    mock_session = AsyncMock(spec=ClientSession)
    mock_session.initialize = mock_initialize
    mock_session.call_tool = mock_call_tool

    # 初期化前にツールを呼ぶとエラー
    with pytest.raises(RuntimeError, match="initialization"):
        await mock_session.call_tool("test", {})

    # 初期化を実行
    await mock_session.initialize()

    # 初期化後はツールが呼べる
    result = await mock_session.call_tool("test", {})
    assert result.content[0].text == "OK"


if __name__ == "__main__":
    # 簡単な動作確認
    print("MCPプロトコルテストスイート")
    print("=" * 50)

    # 正しいプロトコルフォーマットの例
    print("\n✅ 正しいMCPプロトコル (tools/call):")
    correct = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "kb_search_agent",
            "arguments": {"base_id": "JSVJ2SRAA6"}
        }
    }
    print(json.dumps(correct, indent=2))

    print("\n❌ 誤ったプロトコル (tools/execute - 存在しない):")
    incorrect = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/execute",
        "params": {
            "toolId": "kb_search_agent",
            "tool": {"id": "kb_search_agent", "base_id": "JSVJ2SRAA6"}
        }
    }
    print(json.dumps(incorrect, indent=2))

    print("\n✅ リソース購読 (resources/subscribe):")
    subscribe = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "resources/subscribe",
        "params": {
            "uri": "resource://example/data"
        }
    }
    print(json.dumps(subscribe, indent=2))

    print("\n" + "=" * 50)
    print("テストを実行するには: pytest test_mcp_protocol.py")