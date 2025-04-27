# app/tools/sample_math_tools.py
from fastmcp import FastMCP   # 型ヒント用（任意）

def register(mcp: FastMCP):
    """
    auto_register_modules() から渡される FastMCP インスタンスに
    ツールを登録するエントリーポイント。
    """

    @mcp.tool(                       # ← ここで mcp にぶら下げる
        name="add",                  # (オプション) ツール名を明示
        description="2つの数字を加算するツール"
    )
    def add(a: int, b: int) -> int:
        return a + b