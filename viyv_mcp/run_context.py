"""Runtime-context interface shared by Agents SDK wrappers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RunContext(ABC):
    """汎用ランタイムコンテキストの抽象基底クラス"""

    # -------------------------------------------------------------- #
    # インタフェース
    # -------------------------------------------------------------- #
    @abstractmethod
    async def post_start_message(self) -> None:  # pragma: no cover
        """「処理を開始しました …」等、最初に 1 回だけ送るメッセージ"""
        ...

    @abstractmethod
    async def update_progress(self, text: str) -> None:  # pragma: no cover
        """進行状況を既存メッセージへ上書き表示"""
        ...

    @abstractmethod
    async def post_new_message(self, text: str) -> None:  # pragma: no cover
        """スレッドへ追加メッセージを投稿 (画像処理完了後など)"""
        ...