import uvicorn

try:
    from viyv_mcp import ViyvMCP
except ImportError:
    raise

from app.config import Config

def main():
    # 環境変数から stateless_http 設定を読み込む
    stateless_http = Config.get_stateless_http() if hasattr(Config, 'get_stateless_http') else None
    app = ViyvMCP("My SSE MCP Server", stateless_http=stateless_http).get_app()
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)

if __name__ == "__main__":
    main()