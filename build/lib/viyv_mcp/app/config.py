# File: app/config.py
import os

class Config:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))

    # 外部MCPサーバーの設定ファイルを格納するディレクトリ
    # プロジェクト構成にあわせて好きなパスを指定
    BRIDGE_CONFIG_DIR = os.getenv("BRIDGE_CONFIG_DIR", "app/mcp_server_configs")