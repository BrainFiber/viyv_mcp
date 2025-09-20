#!/usr/bin/env python3
"""
MCPサーバーの動作確認テストクライアント
tools/callが正しく動作することを確認します
"""

import json
import httpx
import asyncio
from typing import Dict, Any


async def test_mcp_protocol():
    """MCPプロトコルの動作確認"""

    base_url = "http://localhost:8000/mcp/"  # 末尾のスラッシュが重要

    # MCPはSSE (Server-Sent Events) を使用するため、適切なヘッダーが必要
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("MCPサーバー動作確認テスト")
        print("=" * 60)

        # 1. 初期化リクエスト
        print("\n1. 初期化リクエスト (initialize)")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"listChanged": True}
                }
            }
        }

        try:
            response = await client.post(base_url, json=init_request, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. tools/list リクエスト
        print("\n2. ツール一覧取得 (tools/list)")
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        try:
            response = await client.post(base_url, json=list_request, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    tools = result["result"]["tools"]
                    print(f"利用可能なツール数: {len(tools)}")
                    for tool in tools[:5]:  # 最初の5個だけ表示
                        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        except Exception as e:
            print(f"Error: {e}")

        # 3. tools/call リクエスト（正しい形式）
        print("\n3. ツール呼び出し (tools/call) - 正しい形式")
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add",
                "arguments": {
                    "a": 5,
                    "b": 3
                }
            }
        }

        print(f"Request: {json.dumps(call_request, indent=2)}")
        try:
            response = await client.post(base_url, json=call_request, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
                if "result" in result:
                    print(f"✅ 計算結果: 5 + 3 = {result['result'].get('content', [{}])[0].get('text', 'N/A')}")
        except Exception as e:
            print(f"Error: {e}")

        # 4. 誤ったリクエスト形式のテスト（tools/execute）
        print("\n4. 誤った形式のテスト (tools/execute) - エラーになるべき")
        incorrect_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/execute",  # 誤ったメソッド名
            "params": {
                "toolId": "add",  # 誤ったパラメータ名
                "tool": {
                    "id": "add",
                    "a": 5,
                    "b": 3
                }
            }
        }

        print(f"Request: {json.dumps(incorrect_request, indent=2)}")
        try:
            response = await client.post(base_url, json=incorrect_request, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(f"❌ 期待通りエラー (Status: {response.status_code})")
            else:
                result = response.json()
                if "error" in result:
                    print(f"❌ 期待通りエラー: {result['error'].get('message', 'Unknown error')}")
                else:
                    print(f"⚠️ 予期しない成功: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

        # 5. 別のツールのテスト (multiply)
        print("\n5. 別のツール呼び出し (multiply)")
        multiply_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "multiply",
                "arguments": {
                    "x": 4,
                    "y": 7,
                    "z": 2
                }
            }
        }

        print(f"Request: {json.dumps(multiply_request, indent=2)}")
        try:
            response = await client.post(base_url, json=multiply_request, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    print(f"✅ 計算結果: 4 × 7 × 2 = {result['result'].get('content', [{}])[0].get('text', 'N/A')}")
        except Exception as e:
            print(f"Error: {e}")

        print("\n" + "=" * 60)
        print("テスト完了")
        print("=" * 60)


if __name__ == "__main__":
    print("MCPサーバーが http://localhost:8000 で起動していることを確認してください")
    asyncio.run(test_mcp_protocol())