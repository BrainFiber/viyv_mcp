import uvicorn
import logging
from dotenv import load_dotenv

load_dotenv()

# ログ設定
import os
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    from viyv_mcp import ViyvMCP
except ImportError:
    raise

from app.config import Config

def main():
    # 環境変数から stateless_http 設定を読み込む
    stateless_http = Config.get_stateless_http()
    app = ViyvMCP("My SSE MCP Server", stateless_http=stateless_http).get_app()
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )

if __name__ == "__main__":
    main()