"""
ChatGPT MCP連携に必須のsearchとfetchツール実装
ChatGPTとの接続のためのみに必要な最小限の実装
"""
from typing import Dict, Any, Annotated
from viyv_mcp import tool
from viyv_mcp.run_context import RunContext
from agents import RunContextWrapper
from pydantic import Field
from fastmcp import FastMCP
import logging

logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
    """MCPにツールを登録"""
    logger.info("Registering ChatGPT required tools (search/fetch)...")

    @tool(
        description="Search the data source and return lightweight results",
        tags={"search", "chatgpt", "required"}
    )
    async def search(
        wrapper: RunContextWrapper[RunContext],
        query: Annotated[
            str,
            Field(
                description="ユーザーの検索クエリ",
            ),
        ],
    ) -> Dict[str, Any]:
        """Search for resources matching the query"""
        logger.info(f"search called with query: {query}")
        
        # ChatGPT接続のためのダミー実装
        # 実際の検索処理は不要とのことなので、最小限のレスポンスを返す
        results = []
        
        # ダミーの検索結果を作成（ChatGPTの仕様に準拠）
        for i in range(3):
            results.append({
                "type": "resource_link",
                "id": f"dummy-{i+1}",  # fetchが受け取るID
                "title": f"Sample Result {i+1}",
                "snippet": f"This is a sample search result for query: {query}",
                "uri": f"kb://dummy-{i+1}",
                "mimeType": "text/plain"
            })
        
        logger.info(f"Search completed with {len(results)} dummy results")
        return {"content": results}
    
    @tool(
        description="Fetch full content for a result returned by search",
        tags={"fetch", "chatgpt", "required"}
    )
    async def fetch(
        wrapper: RunContextWrapper[RunContext],
        id: Annotated[
            str,
            Field(
                description="ID returned by search",
            ),
        ],
    ) -> Dict[str, Any]:
        """Fetch the content of a resource by its ID"""
        logger.info(f"fetch called with id: {id}")
        
        # ChatGPT接続のためのダミー実装
        # 実際のフェッチ処理は不要とのことなので、最小限のレスポンスを返す
        
        # IDに基づいてダミーコンテンツを返す
        if id.startswith("dummy-"):
            content = f"This is the full content for {id}. Lorem ipsum dolor sit amet, consectetur adipiscing elit."
            
            return {
                "content": [{
                    "type": "text",
                    "text": content
                }]
            }
        else:
            # 不明なIDの場合
            return {
                "content": [{
                    "type": "text",
                    "text": f"Resource not found: {id}"
                }]
            }