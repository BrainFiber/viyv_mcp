import uvicorn

try:
    from viyv_mcp import ViyvMCP
except ImportError:
    raise

from app.config import Config

def main():
    app = ViyvMCP("My SSE MCP Server").get_app()
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)

if __name__ == "__main__":
    main()