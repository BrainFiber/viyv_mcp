# viyv_mcp v0.1.14 リリースのお知らせ 📢

こんにちは、viyv_mcpユーザーの皆様

viyv_mcp v0.1.14をリリースしました！今回のアップデートでは、v0.1.13で導入したツールグループ化機能の実装例とドキュメントを大幅に追加しました。

## 🎯 今回のアップデートの目的

v0.1.13でツールグループ化機能を実装しましたが、「実際にどう使えば良いの？」という声を多くいただきました。そこで今回、**実践的な実装例と詳細なドキュメント**を追加することで、この強力な機能をすぐに活用できるようにしました。

## ✨ 何が変わったの？

### 1. 充実した実装例

`example/test`プロジェクトに、以下の実装例を追加しました：

- **計算ツール**: `add`（加算）、`subtract`（減算）、`multiply`（乗算）
- **統計ツール**: `average`（平均値計算）
- **Web検索**: `search`（検索）、`fetch`（コンテンツ取得）
- **画像ツール**: `generate_image`、`edit_image`、`variation_image`

合計9個のツールに、適切な`group`と`title`パラメータが設定されています。

### 2. 外部MCPサーバーの実例

Playwright MCPサーバー（20個のブラウザ自動化ツール）を使った、外部MCPサーバーのグループ化例を追加しました。

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

### 3. 詳細なドキュメント

- **GROUPING_IMPLEMENTATION.md**: 実装の詳細と検証結果
- **mcp_server_configs/README.md**: 外部MCPサーバーの設定ガイド
- サンプル設定ファイル（学習用）

## 🚀 すぐに試せます！

```bash
# アップデート
pip install --upgrade viyv_mcp

# 実装例を確認
cd example/test
cat GROUPING_IMPLEMENTATION.md

# サーバーを起動して確認
uv sync
uv run python main.py
```

MCP InspectorやClaude Desktopで接続すると、ツールが綺麗にグループ化されて表示されます！

## 💡 なぜツールグループ化が重要？

大規模なMCPサーバーでは、数十〜数百のツールを提供することがあります。グループ化により：

✅ **見つけやすさ向上**: 必要なツールをすぐに発見
✅ **使いやすいUI**: クライアントアプリでの表示が整理される
✅ **開発効率化**: ツールの役割が一目瞭然
✅ **保守性向上**: 機能ごとの整理で管理が容易

## 📚 ツールグループ化機能の使い方

### 基本的な使い方（内部ツール）

```python
from viyv_mcp import tool

@tool(
    description="2つの数字を加算するツール",
    group="計算ツール",  # ← グループ名を指定
    title="加算"         # ← UI表示名を指定（オプション）
)
def add(a: int, b: int) -> int:
    return a + b
```

### 外部MCPサーバーのグループ化

`app/mcp_server_configs/`内のJSONファイルに`group`フィールドを追加：

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
  "group": "ファイルシステム",
  "group_map": {
    "read_file": "ファイル操作/読み込み",
    "write_file": "ファイル操作/書き込み"
  }
}
```

### 仕組み

- グループ情報は`_meta.viyv.group`（ベンダー名前空間）に格納
- MCP仕様（2024-11-05）に完全準拠
- 後方互換性あり：グループなしツールも正常動作

## 📖 詳しく知りたい方へ

- [PyPI パッケージページ](https://pypi.org/project/viyv-mcp/0.1.14/)
- [GitHub リリースノート](https://github.com/BrainFiber/viyv_mcp/releases/tag/v0.1.14)
- [実装例ディレクトリ](https://github.com/BrainFiber/viyv_mcp/tree/main/example/test)

## 🛠️ 既存プロジェクトへの適用

既にviyv_mcpを使用している場合、以下の手順でグループ化を導入できます：

1. **パッケージのアップデート**
   ```bash
   pip install --upgrade viyv_mcp
   ```

2. **ツールにグループを追加**
   ```python
   # Before
   @tool(description="Add two numbers")
   def add(a: int, b: int) -> int:
       return a + b

   # After
   @tool(description="Add two numbers", group="計算ツール")
   def add(a: int, b: int) -> int:
       return a + b
   ```

3. **動作確認**
   - サーバーを再起動
   - MCP InspectorまたはClaude Desktopで接続
   - ツールがグループ化されて表示されることを確認

## 🙏 フィードバックをお待ちしています

ツールグループ化機能を試してみて、ご意見やご要望がありましたら、ぜひお聞かせください！

- **GitHub Issues**: https://github.com/BrainFiber/viyv_mcp/issues
- **Email**: hiroki.takezawa@brainfiber.net
- **Discussions**: https://github.com/BrainFiber/viyv_mcp/discussions

## 🎁 次回予告

今後のバージョンでは、以下の機能を検討しています：

- WebSocketサポート
- 認証/認可機能
- ツールバージョニング
- パフォーマンス監視ダッシュボード

皆様からのフィードバックを参考に、より使いやすいライブラリを目指します。

それでは、v0.1.14をお楽しみください！🎉

---

**viyv_mcp開発チーム**
Hiroki Takezawa
hiroki.takezawa@brainfiber.net
