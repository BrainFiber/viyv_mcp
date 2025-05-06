

# --- 正規表現パターンの準備 ---
import re


CODE_BLOCK_PATTERN = re.compile(r'```(.+?)```', re.DOTALL)  # triple backticks: ```...```
INLINE_CODE_PATTERN = re.compile(r'`([^`]+?)`', re.DOTALL)  # single backticks: `...`

def convert_markdown_to_slack(text):
    """
    MarkdownをSlackのmrkdwn形式に変換する。
    - コードブロックやインラインコードを保持しつつ、見出し/箇条書きなどをSlack用に整形。
    - インラインコード（`...`）や単一アスタリスク(*...*) の前後に必ず半角スペースを1つ入れる。
    - ダブルアスタリスク(**...**)は先に処理し、単一アスタリスク(*...*)と区別。
    - 最後に連続スペースを1つにまとめる。
    """

    # (1) コードブロック ```...``` をプレースホルダに退避
    code_blocks = []
    def _codeblock_replacer(match):
        code_block_text = match.group(0)  # ```...``` まるごと取得
        code_blocks.append(code_block_text)
        placeholder = f"{{CODE_BLOCK_{len(code_blocks)-1}}}"
        return placeholder

    text = CODE_BLOCK_PATTERN.sub(_codeblock_replacer, text)

    # (2) インラインコード `...` をプレースホルダに退避
    inline_codes = []
    def _inlinecode_replacer(match):
        # match.group(0) -> `リテラル全部` (例: `requests`)
        inline_code_text = match.group(0)
        inline_codes.append(inline_code_text)
        placeholder = f"{{INLINE_CODE_{len(inline_codes)-1}}}"
        return placeholder

    text = INLINE_CODE_PATTERN.sub(_inlinecode_replacer, text)

    # (3) 見出し (# ~ ######) を Slack で「太字 + 改行」に変換
    #     例: # 見出し -> \n*見出し*\n
    text = re.sub(
        r'^(#{1,6})\s*(.*)$',
        lambda m: f"\n*{m.group(2)}*\n",
        text,
        flags=re.MULTILINE
    )

    # (4) ダブルアスタリスク（**...**）を Slack形式(*...*) に変換 (先にやる)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # (4.5) 単一アスタリスク（*...*）の前後に半角スペースを入れる
    #        例: "*必要なライブラリ*" -> " *必要なライブラリ* "
    #        ダブルアスタリスクは既に処理済みなので、ここでは単一アスタリスクのみマッチ
    SINGLE_ASTERISK_PATTERN = re.compile(r'(?<!\*)\*([^*]+?)\*(?!\*)', re.DOTALL)
    text = SINGLE_ASTERISK_PATTERN.sub(r' *\1* ', text)

    # (5) 箇条書き (- ) を Slackで見やすいように "• " に変換
    text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)

    # (6) 一時退避したインラインコードを復元し、前後に必ずスペース1文字ずつ入れる
    #     例: `requests` -> " `requests` "
    for i, inline_code_text in enumerate(inline_codes):
        code_stripped = inline_code_text.strip()   # 念のため余分な空白を除去
        new_code = f" {code_stripped} "            # 両端にスペース
        placeholder = f"{{INLINE_CODE_{i}}}"
        text = text.replace(placeholder, new_code)

    # (7) 一時退避したコードブロックを復元
    for i, code_block_text in enumerate(code_blocks):
        placeholder = f"{{CODE_BLOCK_{i}}}"
        text = text.replace(placeholder, code_block_text)

    # (8) 最後に連続するスペースを1つにまとめる (例: "   " -> " ")
    text = re.sub(r' +', ' ', text)

    return text