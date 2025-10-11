# MCP Server Configurations

このディレクトリには外部MCPサーバーの設定ファイルを配置します。

**注意**: `.example` 拡張子のファイルは読み込まれません。実際に使用する場合は `.json` にリネームしてください。

## v0.1.13 新機能: ツールグループ化

各設定ファイルで `group` と `group_map` フィールドを使用してツールをグループ化できます。

### 基本的な使い方

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
  "group": "ファイルシステム",
  "tags": ["filesystem", "io"]
}
```

### 個別ツールのグループ上書き

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
  "group": "ファイルシステム",
  "group_map": {
    "read_file": "ファイル操作/読み込み",
    "write_file": "ファイル操作/書き込み",
    "list_directory": "ファイル操作/一覧"
  },
  "tags": ["filesystem", "io"]
}
```

## グループ情報の確認

グループ情報は `_meta.viyv.group` フィールドに格納されます（MCPプロトコル準拠）。

### tools/list レスポンス例

```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "ファイルを読み込む",
      "inputSchema": { ... },
      "_meta": {
        "viyv": {
          "group": "ファイル操作/読み込み"
        }
      }
    }
  ]
}
```
