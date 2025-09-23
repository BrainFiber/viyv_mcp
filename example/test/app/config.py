import os

class Config:
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

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