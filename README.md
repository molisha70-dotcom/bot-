
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
