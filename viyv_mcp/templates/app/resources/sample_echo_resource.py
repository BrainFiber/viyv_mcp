# app/resources/sample_echo_resource.py
from mcp.server.fastmcp import FastMCP

def register(mcp: FastMCP):
    @mcp.resource("echo://{message}")
    def echo_resource(message: str) -> str:
        """入力されたメッセージをそのまま返すリソース"""
        return f"Echo: {message}"