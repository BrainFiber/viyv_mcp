# mcp_factory.py
"""McpServer インスタンス生成 + モジュール自動登録"""
import logging

from viyv_mcp.server import McpServer
from viyv_mcp.app.registry import auto_register_modules

logger = logging.getLogger(__name__)

_MODULE_PACKAGES = (
    "app.tools",
    "app.resources",
    "app.prompts",
    "app.agents",
    "app.entries",
)


def create_mcp_server(server_name: str, lifespan) -> McpServer:
    """McpServer を生成し、ローカル modules を自動登録して返す。"""
    from viyv_mcp import __version__

    mcp = McpServer(server_name, version=__version__, lifespan=lifespan)

    for pkg in _MODULE_PACKAGES:
        auto_register_modules(mcp, pkg)

    logger.info("ViyvMCP: MCP server created & local modules registered.")
    return mcp
