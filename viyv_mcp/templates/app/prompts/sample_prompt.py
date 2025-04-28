# app/prompts/sample_prompt.py
from fastmcp import FastMCP
from viyv_mcp import prompt

def register(mcp: FastMCP):
    @prompt()
    def sample_prompt(query: str) -> str:
        """
        ユーザーの質問に対して、そのまま返すプロンプトの例。
        ※実際には、より複雑なテンプレート処理が可能です。
        """
        return f"Your query is: {query}"