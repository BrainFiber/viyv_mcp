# File: app/config.py
import os

class Config:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))

    # 外部MCPサーバーの設定ファイルを格納するディレクトリ
    # プロジェクト構成にあわせて好きなパスを指定
    BRIDGE_CONFIG_DIR = os.getenv("BRIDGE_CONFIG_DIR", "app/mcp_server_configs")

    # WebSocket Bridge settings
    WS_BRIDGE_ENABLED = os.getenv("WS_BRIDGE_ENABLED", "true").lower() in ("true", "1", "yes")
    RELAY_KEY_TTL_HOURS = float(os.getenv("RELAY_KEY_TTL_HOURS", "24"))
    RELAY_KEY_STORAGE = os.getenv("RELAY_KEY_STORAGE", "data/relay_keys.json")

    # FastMCP stateless_http オプション (環境変数から読み込み)
    # "true", "1", "yes" などは True として扱う
    @staticmethod
    def get_stateless_http():
        env_val = os.getenv("STATELESS_HTTP", "").lower()
        if env_val in ("true", "1", "yes", "on"):
            return True
        elif env_val in ("false", "0", "no", "off"):
            return False
        return None  # 未設定の場合