# Claude CLI Tool 使用方法

## セッション管理について

このツールは会話履歴を保持するためにセッション管理機能を提供しています。

### 基本的な使い方

1. **新規セッション（context_id未指定）**
   ```
   claude_cli(prompt="test.txtを表示して")
   ```
   → 新しいセッションIDが自動生成されます

2. **セッション継続（context_idを指定）**
   ```
   claude_cli(
     prompt="日本語に変換して", 
     context_id="cli_session_20250623_112814"
   )
   ```
   → 指定したセッションの会話履歴を引き継ぎます

3. **最新セッションを使用**
   ```
   claude_cli(
     prompt="続きをお願い", 
     context_id="latest"
   )
   ```
   → 最後に使用したセッションを自動的に使用します

### セッション管理ツール

- `list_claude_cli_sessions()` - セッション一覧を表示
- 各セッションには以下の情報が保存されます：
  - Context ID（セッション識別子）
  - 最終更新日時
  - 最後の操作内容
  - メッセージ数

### 注意事項

- Claude CLIの`--resume`機能により、新しいsession_idが発行されますが、会話履歴は正しく引き継がれます
- セッション情報は`app/claude_cli_sessions.json`に保存されます
- 作業ディレクトリのデフォルトは`app/claude_workspace/`です