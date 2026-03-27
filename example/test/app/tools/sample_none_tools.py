# app/tools/sample_none_tools.py
"""
何もしないツールのサンプルセット。
"""

from typing import Annotated, List

from pydantic import Field
from viyv_mcp import tool


def register(mcp):  # auto_register_modules から呼ばれる
    # --------------------------------------------------------------------- #
    # 1) add
    # --------------------------------------------------------------------- #
    @tool(description="何もしない", tags={"none"})
    def none() -> int:
        """何もしない"""
        return 0
