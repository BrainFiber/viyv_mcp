# app/resources/sample_echo_resource.py
from fastmcp import FastMCP
from viyv_mcp import resource

def register(mcp: FastMCP):
    @resource("echo://{message}")
    def echo_resource(message: str) -> str:
        """入力されたメッセージをそのまま返すリソース"""
        return f"Echo: {message}"