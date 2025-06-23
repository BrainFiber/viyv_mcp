# app/tools/sample_none_tools.py
"""
何もしないツールのサンプルセット。
"""

from typing import Annotated, List

from agents import RunContextWrapper
from pydantic import Field
from fastmcp import FastMCP   # 型ヒント用（任意）
from viyv_mcp import tool
from viyv_mcp.run_context import RunContext


def register(mcp: FastMCP):  # auto_register_modules から呼ばれる
    # --------------------------------------------------------------------- #
    # 1) add
    # --------------------------------------------------------------------- #
    @tool(description="何もしない", tags={"none"})
    def none(
        wrapper: RunContextWrapper[RunContext],
    ) -> int:
        """何もしない"""
        return 0
