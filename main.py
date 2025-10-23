
import os, threading
from bot import run_bot

# ---- Flask keepalive (Render Web Service向け) ----
# Web Service としてデプロイする場合、Render が $PORT へのバインドを要求するため、
# 軽量なHTTPサーバ(Flask)をバックグラウンドで立ち上げます。
try:
    from flask import Flask, jsonify
except Exception:
    Flask = None

def run_keepalive():
    if Flask is None:
        print("Flask not installed. If using Render Web Service, add Flask to requirements.txt")
        return
    app = Flask("keepalive")
    @app.get("/")
    def root():
        return jsonify(status="ok"), 200
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # keepalive を別スレッドで起動
    threading.Thread(target=run_keepalive, daemon=True).start()
    # Discord Bot を起動
    run_bot()
