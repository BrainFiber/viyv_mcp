# app/tools/sample_math_tools.py
from mcp.server.fastmcp import FastMCP

def register(mcp: FastMCP):
    @mcp.tool()
    def add(a: int, b: int) -> int:
        """2つの数字を加算するツール"""
        return a + b