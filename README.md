# Discord Announcer Bot (Final User Version)

このBotは Discord サーバー内で「📢や【告知】を含む投稿」を自動的に
**監視元チャンネル → 転移先チャンネル** にミラーする完全自動Botです。

## 設定（この構成）

| 項目 | 設定値 |
|------|---------|
| Guild ID | 1046742748641894441 |
| 監視元 | 1430892332873551872 |
| 転移先 | 1430898031770861672 |

## 使い方

1. `.env` に Discord Bot のトークンを設定
2. Bot に「メッセージ内容の意図」(Message Content Intent) を有効化
3. 権限：送信、埋め込みリンク、履歴閲覧、閲覧
4. `pip install -r requirements.txt` → `python main.py` で起動
5. 監視元チャンネルに「📢」「【告知】」「開催」などを含む投稿をすると転移先に自動ミラーされます

## デプロイ

Render で GitHub Blueprint としてデプロイ可（render.yaml 同梱）。
