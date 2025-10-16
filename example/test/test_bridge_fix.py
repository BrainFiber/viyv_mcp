"""
AWS MCP servers compatibility fix の動作確認テスト

修正内容:
- ListResourcesResult から .resources 属性を正しく取得
- ListPromptsResult から .prompts 属性を正しく取得
- meta, nextCursor フィールドをリソースとして扱わない
"""

import asyncio
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock
from mcp import types
from viyv_mcp.app.bridge_manager import (
    _safe_list_resources,
    _safe_list_prompts,
    _get_resource_uri,
)


def test_get_resource_uri():
    """URI 互換性ヘルパー関数のテスト"""
    print("\n=== Test 1: _get_resource_uri() ===")

    # 新仕様（uri 属性）のテスト
    resource_new = types.Resource(
        uri="file://test.txt",
        name="test",
        description="Test resource"
    )
    uri = _get_resource_uri(resource_new)
    print(f"✓ New style (uri): {uri}")
    # MCP SDK が自動的に末尾に / を追加する可能性があるため、文字列化してチェック
    uri_str = str(uri)
    assert "file://test.txt" in uri_str, f"Expected URI to contain 'file://test.txt', got '{uri_str}'"

    print("✓ _get_resource_uri() test passed")


async def test_safe_list_resources():
    """Resources リスト取得の修正テスト"""
    print("\n=== Test 2: _safe_list_resources() ===")

    # モックセッションを作成
    mock_session = MagicMock()

    # MCP Protocol 仕様に準拠したレスポンスを作成
    # ListResourcesResult: {resources: [...], meta: {...}, nextCursor: "..."}
    mock_result = types.ListResourcesResult(
        resources=[
            types.Resource(
                uri="aws://cost-explorer/summary",
                name="cost_summary",
                description="AWS Cost Summary"
            ),
            types.Resource(
                uri="aws://cost-explorer/detailed",
                name="cost_detailed",
                description="AWS Detailed Costs"
            ),
        ],
        meta={"version": "1.0"},  # これが以前はエラーの原因だった
        nextCursor="next_page_token_12345"  # これも以前はエラーの原因だった
    )

    # list_resources を AsyncMock でモック
    mock_session.list_resources = AsyncMock(return_value=mock_result)

    # 実行
    resources = await _safe_list_resources(mock_session, "billing-cost-management")

    # 検証
    print(f"✓ Returned {len(resources)} resources")
    assert len(resources) == 2, f"Expected 2 resources, got {len(resources)}"

    assert "aws://cost-explorer/summary" in str(resources[0].uri)
    assert resources[0].name == "cost_summary"
    print(f"✓ Resource 1: {resources[0].name} - {resources[0].uri}")

    assert "aws://cost-explorer/detailed" in str(resources[1].uri)
    assert resources[1].name == "cost_detailed"
    print(f"✓ Resource 2: {resources[1].name} - {resources[1].uri}")

    print("✓ _safe_list_resources() test passed")


async def test_safe_list_prompts():
    """Prompts リスト取得の修正テスト"""
    print("\n=== Test 3: _safe_list_prompts() ===")

    # モックセッションを作成
    mock_session = MagicMock()

    # MCP Protocol 仕様に準拠したレスポンスを作成
    # ListPromptsResult: {prompts: [...], meta: {...}, nextCursor: "..."}
    mock_result = types.ListPromptsResult(
        prompts=[
            types.Prompt(
                name="analyze_costs",
                description="Analyze AWS costs",
                arguments=[
                    {"name": "start_date", "type": "string", "required": True},
                    {"name": "end_date", "type": "string", "required": True},
                ]
            ),
            types.Prompt(
                name="forecast_costs",
                description="Forecast future costs",
                arguments=[
                    {"name": "months", "type": "integer", "required": False},
                ]
            ),
        ],
        meta={"version": "1.0"},  # これが以前はエラーの原因だった
        nextCursor="next_page_token_67890"  # これも以前はエラーの原因だった
    )

    # list_prompts を AsyncMock でモック
    mock_session.list_prompts = AsyncMock(return_value=mock_result)

    # 実行
    prompts = await _safe_list_prompts(mock_session, "billing-cost-management")

    # 検証
    print(f"✓ Returned {len(prompts)} prompts")
    assert len(prompts) == 2, f"Expected 2 prompts, got {len(prompts)}"

    assert prompts[0].name == "analyze_costs"
    print(f"✓ Prompt 1: {prompts[0].name}")

    assert prompts[1].name == "forecast_costs"
    print(f"✓ Prompt 2: {prompts[1].name}")

    print("✓ _safe_list_prompts() test passed")


async def test_empty_results():
    """空のリソース/プロンプトリストの処理テスト"""
    print("\n=== Test 4: Empty Results ===")

    mock_session = MagicMock()

    # 空のリソースリスト（meta と nextCursor のみ）
    empty_resources = types.ListResourcesResult(
        resources=[],
        meta=None,
        nextCursor=None
    )
    mock_session.list_resources = AsyncMock(return_value=empty_resources)

    resources = await _safe_list_resources(mock_session, "test-server")
    print(f"✓ Empty resources list: {len(resources)} items")
    assert len(resources) == 0

    # 空のプロンプトリスト（meta と nextCursor のみ）
    empty_prompts = types.ListPromptsResult(
        prompts=[],
        meta=None,
        nextCursor=None
    )
    mock_session.list_prompts = AsyncMock(return_value=empty_prompts)

    prompts = await _safe_list_prompts(mock_session, "test-server")
    print(f"✓ Empty prompts list: {len(prompts)} items")
    assert len(prompts) == 0

    print("✓ Empty results test passed")


async def main():
    print("=" * 60)
    print("AWS MCP Servers Compatibility Fix - Verification Tests")
    print("=" * 60)

    try:
        # Test 1: URI 互換性ヘルパー
        test_get_resource_uri()

        # Test 2: Resources リスト取得
        await test_safe_list_resources()

        # Test 3: Prompts リスト取得
        await test_safe_list_prompts()

        # Test 4: 空のリスト
        await test_empty_results()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print("\nConclusion:")
        print("- meta, nextCursor fields are no longer treated as resources/prompts")
        print("- Pagination metadata is properly handled")
        print("- AWS MCP servers should now work correctly")

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())
