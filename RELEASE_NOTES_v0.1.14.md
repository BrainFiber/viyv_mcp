# viyv_mcp v0.1.14 リリース 🎉

## 📦 アップデート方法

```bash
pip install --upgrade viyv_mcp
```

## ✨ 主な変更点

### 実装例とドキュメントの大幅拡充

v0.1.13で実装したツールグループ化機能について、実践的な使用例とドキュメントを大幅に追加しました。

#### 追加された実装例

1. **example/testプロジェクト**
   - 4種類のツールグループの実装例（計算ツール、統計ツール、Web検索、画像ツール）
   - 合計9個のツールに`group`と`title`パラメータを追加
   - すぐに使える実践的なコード例

2. **外部MCPサーバーのグループ化例**
   - Playwright MCPサーバーの完全な設定例（`playwright.json`）
   - 20個のブラウザ自動化ツールを階層的にグループ化
   - `group`と`group_map`の両方を使った高度な設定例

3. **包括的なドキュメント**
   - `GROUPING_IMPLEMENTATION.md`: 実装結果の詳細レポート
   - `app/mcp_server_configs/README.md`: 外部MCPサーバーグループ化ガイド
   - サンプル設定ファイル（`.example`形式）

## 🎯 ツールグループ化機能とは？

v0.1.13で導入されたこの機能により、MCPツールを論理的なグループに整理できます。

### 基本的な使い方

```python
from viyv_mcp import tool

@tool(
    description="2つの数字を加算するツール",
    group="計算ツール",  # ← グループ名
    title="加算"         # ← UI表示名
)
def add(a: int, b: int) -> int:
    return a + b
```

### 外部MCPサーバーのグループ化

```json
{
  "name": "playwright",
  "command": "npx-for-claude",
  "args": ["@playwright/mcp@latest"],
  "group": "ブラウザ自動化",
  "group_map": {
    "playwright_navigate": "ブラウザ/ナビゲーション",
    "playwright_screenshot": "ブラウザ/スクリーンショット",
    "playwright_click": "ブラウザ/操作"
  }
}
```

## 📊 実装結果

検証済みの実装例：
- **ツールグループ数**: 4種類
- **グループ化されたツール**: 9個（内部ツール） + 20個（Playwright）
- **MCP仕様準拠**: `_meta.viyv.group`ベンダー名前空間を使用
- **後方互換性**: グループなしツールも正常動作

## 🚀 既存プロジェクトへの適用方法

### 手順1: パッケージのアップデート
```bash
pip install --upgrade viyv_mcp
```

### 手順2: ツールにグループを追加
```python
# Before (v0.1.12以前)
@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

# After (v0.1.13+)
@tool(
    description="Add two numbers",
    group="計算ツール",
    title="加算"
)
def add(a: int, b: int) -> int:
    return a + b
```

### 手順3: 外部MCPサーバー設定の更新（オプション）
`app/mcp_server_configs/`内のJSONファイルに`group`フィールドを追加します。

## 📚 参考資料

- [実装例: example/test/GROUPING_IMPLEMENTATION.md](example/test/GROUPING_IMPLEMENTATION.md)
- [設定ガイド: example/test/app/mcp_server_configs/README.md](example/test/app/mcp_server_configs/README.md)
- [PyPI: viyv_mcp v0.1.14](https://pypi.org/project/viyv-mcp/0.1.14/)

## 🔄 変更されたファイル

- `pyproject.toml` - バージョン更新
- `viyv_mcp/__init__.py` - バージョン更新
- `example/test/app/tools/*.py` - グループ追加
- `example/test/app/mcp_server_configs/` - 新規作成
- `example/test/GROUPING_IMPLEMENTATION.md` - 新規作成

## 💡 次のステップ

1. `pip install --upgrade viyv_mcp`でアップデート
2. `example/test/`ディレクトリの実装例を確認
3. 既存のツールに`group`パラメータを追加
4. MCP InspectorやClaude Desktopで表示を確認

---

**Full Changelog**: https://github.com/BrainFiber/viyv_mcp/compare/v0.1.13...v0.1.14
