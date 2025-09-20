#!/usr/bin/env python3
"""
正しいMCPクライアントのテスト

MCPサーバーに対して標準的なMCPプロトコルを使用して通信します。
session.initialize()を含む完全なフローをテストします。
"""

import asyncio
import json
from typing import Any, Dict

from mcp import ClientSession, types
from mcp.client.sse import sse_client


async def test_mcp_with_correct_client():
    """標準的なMCPクライアントを使用したテスト"""

    server_url = "http://localhost:8000/mcp/"

    print("=" * 60)
    print("正しいMCPクライアントでの動作確認")
    print("=" * 60)

    try:
        # SSEクライアントを使用して接続
        async with sse_client(server_url) as (read_stream, write_stream):
            # セッションを作成
            session = ClientSession(read_stream, write_stream)

            # セッションを開始
            await session.__aenter__()

            print("\n1. 初期化 (session.initialize)")
            try:
                # 正しい初期化リクエスト
                # MCPクライアントSDKが自動的にclientInfoを設定
                result = await session.initialize()

                print(f"✅ 初期化成功!")
                print(f"   プロトコルバージョン: {result.protocolVersion}")
                if result.serverInfo:
                    print(f"   サーバー名: {result.serverInfo.name}")
                    print(f"   サーバーバージョン: {result.serverInfo.version}")
                print(f"   ツールサポート: {result.capabilities.tools is not None}")
                print(f"   リソースサポート: {result.capabilities.resources is not None}")

            except Exception as e:
                print(f"❌ 初期化失敗: {e}")
                return

            print("\n2. ツール一覧取得 (session.list_tools)")
            try:
                tools = await session.list_tools()
                print(f"✅ ツール一覧取得成功: {len(tools.tools)}個のツール")

                # 最初の5個のツールを表示
                for tool in tools.tools[:5]:
                    print(f"   - {tool.name}: {tool.description}")

            except Exception as e:
                print(f"❌ ツール一覧取得失敗: {e}")

            print("\n3. ツール呼び出し (session.call_tool) - add")
            try:
                # addツールを呼び出し
                result = await session.call_tool(
                    "add",
                    arguments={"a": 10, "b": 20}
                )

                print(f"✅ ツール呼び出し成功!")
                # 結果を表示
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"   結果: 10 + 20 = {content.text}")
                    elif hasattr(content, 'data'):
                        print(f"   結果: {content.data}")

            except Exception as e:
                print(f"❌ ツール呼び出し失敗: {e}")

            print("\n4. 別のツール呼び出し (multiply)")
            try:
                # multiplyツールを呼び出し
                result = await session.call_tool(
                    "multiply",
                    arguments={"x": 3, "y": 7, "z": 2}
                )

                print(f"✅ ツール呼び出し成功!")
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"   結果: 3 × 7 × 2 = {content.text}")
                    elif hasattr(content, 'data'):
                        print(f"   結果: {content.data}")

            except Exception as e:
                print(f"❌ ツール呼び出し失敗: {e}")

            print("\n5. リソース一覧取得 (session.list_resources)")
            try:
                resources = await session.list_resources()
                print(f"✅ リソース一覧取得成功: {len(resources.resources)}個のリソース")

                # 最初の3個のリソースを表示
                for resource in resources.resources[:3]:
                    print(f"   - {resource.uri}: {resource.description}")

            except Exception as e:
                print(f"❌ リソース一覧取得失敗: {e}")

            print("\n6. プロンプト一覧取得 (session.list_prompts)")
            try:
                prompts = await session.list_prompts()
                print(f"✅ プロンプト一覧取得成功: {len(prompts.prompts)}個のプロンプト")

                # 最初の3個のプロンプトを表示
                for prompt in prompts.prompts[:3]:
                    print(f"   - {prompt.name}: {prompt.description}")

            except Exception as e:
                print(f"❌ プロンプト一覧取得失敗: {e}")

            # セッションを終了
            await session.__aexit__(None, None, None)

    except Exception as e:
        print(f"\n❌ クライアント接続エラー: {e}")
        print("   サーバーが http://localhost:8000 で起動していることを確認してください")

    print("\n" + "=" * 60)
    print("テスト完了")
    print("=" * 60)


async def test_without_client_info():
    """clientInfoを省略したinitializeリクエストのテスト（パッチが効いているか確認）"""

    import httpx

    print("\n" + "=" * 60)
    print("clientInfo無しでの初期化テスト（パッチの確認）")
    print("=" * 60)

    url = "http://localhost:8000/mcp/"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # clientInfoを含まない初期化リクエスト
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            # clientInfoを省略
            "capabilities": {
                "tools": {"listChanged": True}
            }
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=init_request, headers=headers)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                print("✅ パッチが適用されています: clientInfo無しでも初期化成功")
            else:
                print("❌ パッチが未適用: clientInfo無しでは初期化失敗")
                print(f"Response: {response.text[:200]}")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    print("MCPサーバーが http://localhost:8000 で起動していることを確認してください\n")

    # 正しいMCPクライアントでのテスト
    asyncio.run(test_mcp_with_correct_client())

    # パッチの動作確認
    asyncio.run(test_without_client_info())