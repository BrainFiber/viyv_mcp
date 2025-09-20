"""
MCPプロトコルリクエストインターセプター

HTTPレベルでMCPリクエストを処理し、互換性の問題を解決します。
特に`initialize`リクエストで`clientInfo`が欠落している場合に自動補完を行います。
"""

import json
import logging
from typing import Dict, Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)


class MCPRequestInterceptor(BaseHTTPMiddleware):
    """
    MCPプロトコルのリクエストを傍受し、必要に応じて修正するミドルウェア

    主な機能：
    - initializeリクエストでclientInfoが無い場合にデフォルト値を追加
    - 将来的な互換性問題に対応可能な拡張ポイント
    """

    def __init__(self, app, strict_validation: bool = False):
        """
        Args:
            app: Starletteアプリケーション
            strict_validation: Trueの場合、clientInfo無しをエラーにする（デフォルトはFalse）
        """
        super().__init__(app)
        self.strict_validation = strict_validation

    async def dispatch(self, request: Request, call_next):
        # MCPエンドポイント以外はスキップ
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        # POSTリクエストのみ処理
        if request.method != "POST":
            return await call_next(request)

        try:
            # リクエストボディを読み込む
            body = await request.body()

            # 空のボディはスキップ
            if not body:
                return await call_next(request)

            # JSONをパース
            try:
                json_data = json.loads(body)
            except json.JSONDecodeError:
                # JSON以外のリクエストはそのまま通す
                return await call_next(request)

            # initializeリクエストの処理
            if json_data.get("method") == "initialize":
                modified = self._process_initialize_request(json_data)

                if modified:
                    # 修正されたJSONでリクエストを再構築
                    body = json.dumps(json_data).encode("utf-8")

                    # 新しいリクエストを作成（bodeyを置き換え）
                    async def receive():
                        return {
                            "type": "http.request",
                            "body": body,
                            "more_body": False,
                        }

                    # リクエストのscopeを修正
                    request._receive = receive

                    # Content-Lengthヘッダーを更新
                    headers = MutableHeaders(request.headers)
                    headers["content-length"] = str(len(body))

                    logger.info("MCPRequestInterceptor: clientInfoを自動補完しました")

        except Exception as e:
            logger.error(f"MCPRequestInterceptor: リクエスト処理中にエラー: {e}")
            # エラーが発生してもリクエストは通す

        # 次のミドルウェアまたはアプリケーションを呼び出す
        return await call_next(request)

    def _process_initialize_request(self, json_data: Dict[str, Any]) -> bool:
        """
        initializeリクエストを処理し、必要に応じて修正する

        Args:
            json_data: リクエストのJSONデータ

        Returns:
            修正が行われた場合True
        """
        if "params" not in json_data:
            return False

        params = json_data["params"]

        # clientInfoが無い場合
        if "clientInfo" not in params or params["clientInfo"] is None:
            if self.strict_validation:
                # 厳密モードではエラーにする
                logger.warning("MCPRequestInterceptor: clientInfoが提供されていません（厳密モード）")
                return False

            # デフォルトのclientInfoを追加
            params["clientInfo"] = {
                "name": "unknown-client",
                "version": "0.0.0"
            }

            logger.debug(f"MCPRequestInterceptor: デフォルトclientInfoを追加しました")
            return True

        return False


class AsyncRequestBodyMiddleware(BaseHTTPMiddleware):
    """
    リクエストボディを事前に読み込んで保存するミドルウェア

    Starletteではリクエストボディは一度しか読めないため、
    複数のミドルウェアで使用する場合に必要
    """

    async def dispatch(self, request: Request, call_next):
        # POSTリクエストのみ処理
        if request.method == "POST" and request.url.path.startswith("/mcp"):
            # ボディを読み込んで保存
            body = await request.body()

            # リクエストを再構築
            async def receive():
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }

            request._receive = receive
            request._body = body

        return await call_next(request)