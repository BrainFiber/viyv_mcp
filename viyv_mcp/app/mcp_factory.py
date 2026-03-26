# mcp_factory.py
"""FastMCP インスタンス生成 + モジュール自動登録"""
import logging

from fastmcp import FastMCP
from viyv_mcp.app.registry import auto_register_modules

logger = logging.getLogger(__name__)

_MODULE_PACKAGES = (
    "app.tools",
    "app.resources",
    "app.prompts",
    "app.agents",
    "app.entries",
)


def create_mcp_server(server_name: str, lifespan) -> FastMCP:
    """FastMCP を生成し、ローカル modules を自動登録して返す。"""
    mcp = FastMCP(server_name, lifespan=lifespan)

    for pkg in _MODULE_PACKAGES:
        auto_register_modules(mcp, pkg)

    logger.info("ViyvMCP: MCP server created & local modules registered.")
    return mcp
