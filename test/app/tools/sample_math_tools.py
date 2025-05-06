# app/tools/sample_math_tools.py
"""
基本的な四則演算ツール + 配列平均値ツールのサンプルセット。

各パラメータには `Annotated` + `Field` を付与して
title / description / default 値を JSON-Schema に反映。
"""

from typing import Annotated, List

from pydantic import Field
from fastmcp import FastMCP   # 型ヒント用（任意）
from viyv_mcp import tool


def register(mcp: FastMCP):  # auto_register_modules から呼ばれる
    # --------------------------------------------------------------------- #
    # 1) add
    # --------------------------------------------------------------------- #
    @tool(description="2つの数字を加算するツール", tags={"calc"})
    def add(
        a: Annotated[int, Field(title="被加数", description="1 つ目の整数")],
        b: Annotated[int, Field(title="加数",  description="2 つ目の整数")],
    ) -> int:
        """a + b を計算して返す"""
        return a + b

    # --------------------------------------------------------------------- #
    # 2) subtract
    # --------------------------------------------------------------------- #
    @tool(description="2つの数字を減算するツール", tags={"calc"})
    def subtract(
        minuend: Annotated[int, Field(title="被減数", description="引かれる数")],
        subtrahend: Annotated[int, Field(title="減数", description="引く数")],
    ) -> int:
        """minuend − subtrahend を返す"""
        return minuend - subtrahend

    # --------------------------------------------------------------------- #
    # 3) multiply（3 つ目は省略可でデフォルト 1）
    # --------------------------------------------------------------------- #
    @tool(description="乗算ツール（3 つ目の引数は省略可）", tags={"calc"})
    def multiply(
        x: Annotated[int, Field(title="被乗数1")],
        y: Annotated[int, Field(title="被乗数2")],
        z: Annotated[int, Field(title="被乗数3", description="省略可")] = 1,
    ) -> int:
        """x × y × z を返す（z が省略時は 1）"""
        return x * y * z

    # --------------------------------------------------------------------- #
    # 4) average（配列入力と浮動小数出力）
    # --------------------------------------------------------------------- #
    @tool(description="数列の平均値を求めるツール", tags={"calcXX"})
    def average(
        numbers: Annotated[
            List[float],
            Field(
                title="数列",
                description="平均を取りたい数値のリスト",
                min_items=1,
            ),
        ]
    ) -> float:
        """numbers の平均値（float, 小数点第2位まで）"""
        return round(sum(numbers) / len(numbers), 2)