"""
MCPプロトコルの初期化リクエストに関する互換性修正

一部のMCPクライアントが`clientInfo`フィールドを送信しない問題に対応するため、
InitializeRequestParamsのバリデーションを緩和します。
"""

import logging
from typing import Any, Optional
from pydantic import Field

logger = logging.getLogger(__name__)


def patch_initialize_params():
    """
    InitializeRequestParamsのclientInfoフィールドをオプショナルに変更するパッチ

    MCPプロトコル仕様では`clientInfo`は必須ですが、一部のクライアント実装では
    このフィールドを送信しないため、互換性のために緩和します。
    """
    try:
        from mcp.types import InitializeRequestParams, Implementation

        # Pydantic v2でフィールドをオプショナルに変更
        if 'clientInfo' in InitializeRequestParams.model_fields:
            field = InitializeRequestParams.model_fields['clientInfo']
            # 必須フラグをFalseに設定
            field.is_required = lambda: False
            field.required = False
            # デフォルト値を設定
            field.default = None
            # 型ヒントもOptionalに変更
            field.annotation = Optional[Implementation]

            logger.info("InitializeRequestParams.clientInfo をオプショナルに変更しました")
        else:
            logger.warning("InitializeRequestParams.clientInfo フィールドが見つかりません")

    except ImportError as e:
        logger.error(f"MCP types のインポートに失敗しました: {e}")
    except Exception as e:
        logger.error(f"InitializeRequestParams のパッチ適用に失敗しました: {e}")


def get_default_client_info():
    """
    clientInfoが提供されなかった場合のデフォルト値を生成
    """
    from mcp.types import Implementation

    return Implementation(
        name="unknown-client",
        version="0.0.0"
    )


def monkey_patch_mcp_validation():
    """
    MCPサーバーの初期化バリデーションを緩和する包括的なパッチ

    このパッチは以下の処理を行います：
    1. clientInfoフィールドをオプショナルに変更
    2. 必要に応じてデフォルト値を設定

    Pydantic v2対応：model_validateメソッドをパッチして、
    __pydantic_validator__の読み取り専用制限を回避
    """
    try:
        from mcp.types import InitializeRequestParams

        # オリジナルのmodel_validateメソッドを保存
        original_model_validate = InitializeRequestParams.model_validate

        def patched_model_validate(cls, obj, *, strict=None, from_attributes=None, context=None):
            """カスタムバリデーション：clientInfoが無い場合にデフォルト値を設定"""
            if isinstance(obj, dict) and ('clientInfo' not in obj or obj['clientInfo'] is None):
                # objをコピーして変更（元のobjを変更しないため）
                obj = obj.copy()
                obj['clientInfo'] = {
                    'name': 'unknown-client',
                    'version': '0.0.0'
                }
                logger.debug("clientInfo が提供されなかったため、デフォルト値を設定しました")

            # オリジナルのバリデーションを実行
            return original_model_validate.__func__(cls, obj, strict=strict, from_attributes=from_attributes, context=context)

        # model_validateメソッドをパッチ
        InitializeRequestParams.model_validate = classmethod(patched_model_validate)
        logger.info("MCP初期化バリデーションのパッチを適用しました（model_validate method patched）")

    except Exception as e:
        logger.error(f"MCP初期化バリデーションのパッチ適用に失敗しました: {e}")