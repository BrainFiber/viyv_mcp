# app/prompts/sample_prompt.py
from mcp.server.fastmcp import FastMCP
import mcp.types as types

def register(mcp: FastMCP):
    @mcp.prompt()
    def sample_prompt(query: str) -> str:
        """
        ユーザーの質問に対して、そのまま返すプロンプトの例。
        ※実際には、より複雑なテンプレート処理が可能です。
        """
        return f"Your query is: {query}"