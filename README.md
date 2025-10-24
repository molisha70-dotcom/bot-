
# Discord Announcer (Classic Split)

前の経済Botと同じように、**bot本体**と**起動スクリプト**を分割した構成です。  
Render の Web Service で動かすための **Flask keepalive** も main.py に同梱。

## 構成
```
discord-announcer-classic/
├── bot.py              # Bot本体：イベント処理／自動転移／スラッシュコマンド
├── main.py             # 起動スクリプト：Flask keepalive + run_bot()
├── config.yaml         # 転移条件・テンプレ
├── requirements.txt    # 依存
├── .env.example        # トークン設定サンプル
└── README.md
```

## 固定ID
- Guild: 1046742748641894441
- 監視元: 1430892332873551872
- 転移先: 1430898031770861672

## ローカル実行
```bash
pip install -r requirements.txt
cp .env.example .env  # DISCORD_TOKEN を設定
python main.py
```

## Render (Web Service) デプロイ
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- 環境変数:
  - `DISCORD_TOKEN` （必須）
  - `TZ=Asia/Tokyo`

## 注意
- Discord Developer Portal で **MESSAGE CONTENT INTENT** をONにしてください。
- 権限: 読み取り／履歴閲覧／送信／埋め込みリンク（監視元・転移先ともに）。

## まとめ転送（バッチ配送）の設定
- 監視元チャンネルで転送条件 (`config.yaml` の `transfer.rules`) を満たしたメッセージは、一旦バッファに積まれます。
- `SUMMARY_INTERVAL_MINUTES` 環境変数で指定した分ごとに、同じ転送先チャンネル向けのメッセージが1本の埋め込みにまとめられて送信されます。
  - 例: 2 分ごとにまとめたい場合は、Bot を起動する環境に `SUMMARY_INTERVAL_MINUTES=2` を設定します。
- 設定値を変えた場合は Bot を再起動してください。起動時に値が読み込まれ、Discord の `tasks.loop` がその間隔でスケジュールされるため、稼働中には変更が反映されません。
- バッファに溜まったメッセージは送信後にクリアされ、次のバッチには含まれません。
