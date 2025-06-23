# Project Overview

`viyv_mcp` is a Python package that wraps **FastMCP** and **Starlette**. It lets you generate and run an MCP server with sample tools, resources and prompt definitions.

## Key Features
- CLI `create-viyv-mcp` generates a ready-to-run template project.
- Decorators `@tool`, `@resource`, `@prompt`, `@agent` simplify registration of modules.
- Automatically bridges external MCP servers via JSON config files under `app/mcp_server_configs`.
- Includes optional adapters for Slack and OpenAI Agents.
- Dynamic tool injection keeps tools up to date for entries and agents.

## Quick Start
1. Install the package from PyPI:
   ```bash
   pip install viyv_mcp
   ```
2. Create a new project template:
   ```bash
   create-viyv-mcp new my_mcp_project
   ```
3. Inside the generated directory run:
   ```bash
   uv sync
   uv run python main.py
   ```
The server starts on `0.0.0.0:8000` and automatically registers modules and bridges external servers defined in `app/mcp_server_configs`.

## Configuration
- `Config` (see `viyv_mcp/app/config.py`) exposes environment variables:
  - `HOST` (default `127.0.0.1`)
  - `PORT` (default `8000`)
  - `BRIDGE_CONFIG_DIR` (default `app/mcp_server_configs`)
- `STATIC_DIR` controls the directory for static files (`static/images` by default).

## Usage Notes
- `ViyvMCP` assembles an ASGI app combining Streamable HTTP, static files and custom entries. It mounts FastMCP at `/mcp` by default and handles startup/shutdown of external MCP bridges.
- External MCP servers are launched according to JSON files containing `command`, `args`, and optional environment variables. OS environment variables take precedence.
- Decorator `@entry(path)` registers additional FastAPI apps; `@agent` registers callable tools for OpenAI Agents via `build_function_tools`.
- The package is released under the MIT License.

## Development Knowledge Base

このセクションは、開発時に役立つ知識を記録します。実装の詳細ではなく、今後の開発で参考になる情報のみを記載します。

### MCP Tool開発のポイント

1. **ツールパラメータの型注釈**
   - FastMCPのツールでは`Annotated`と`Field`を使ってパラメータを定義する
   - 例: `query: Annotated[str, Field(description="検索クエリ")]`
   - Optionalパラメータはデフォルト値を設定する

2. **Claude CLI統合**
   - Claude CLIの`--resume`機能はセッションIDを使用して会話を継続する
   - セッションの永続化にはJSON形式でのファイル保存が有効
   - 非同期ファイル操作では`asyncio.Lock()`でファイルアクセスを保護する

3. **ChatGPT互換性要件**
   - ChatGPT連携には必須ツール`search`と`fetch`が必要
   - `search`は`query`パラメータ（必須）を受け取り、`resource_link`形式で結果を返す
   - `fetch`は`id`パラメータ（必須）を受け取る - URIではなくIDである点に注意
   - `annotations`パラメータは現在のviyv_mcpではサポートされていない

4. **ロギング設定**
   - サーバー起動時のログ表示には`logging.basicConfig()`の設定が必要
   - uvicornの`log_level`も適切に設定する

5. **MCPプロトコル**
   - tools/listリクエストには適切なセッションIDが必要
   - initializeリクエストには`protocolVersion`と`capabilities`が必須

### 知識の記録について

今後も開発中に得られた重要な知見は、このAGENTS.mdファイルに記録します。記録する内容は：
- 開発時のベストプラクティス
- よくある問題と解決策のパターン
- API/フレームワークの重要な仕様
- 今後の開発で再利用できる知識

記録しない内容：
- 特定の変更の詳細な履歴
- 一時的な修正内容
- プロジェクト固有の実装詳細

