import os, pytz, yaml, hashlib, threading
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TZ = os.getenv("TZ", "Asia/Tokyo")
JST = pytz.timezone(TZ)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
CFG = load_config()

async def mirror_message(msg, to_ch):
    embed = discord.Embed(
        title="📌 転移されたお知らせ",
        description=(msg.content or "")[:4000],
        color=0x5865F2)
    embed.add_field(
        name="元の投稿",
        value=f"[ジャンプリンク]({msg.jump_url})\n投稿者：{msg.author.mention}／チャンネル：{msg.channel.mention}",
        inline=False)
    if msg.attachments:
        a = msg.attachments[0]
        if a.content_type and a.content_type.startswith("image/"):
            embed.set_image(url=a.url)
    await to_ch.send(embed=embed)

DEDUP_CACHE = deque(maxlen=500)
def recent_seen(guild_id, channel_id, h, window):
    now = datetime.utcnow(); cutoff = now - timedelta(minutes=window)
    while DEDUP_CACHE and DEDUP_CACHE[0][3] < cutoff: DEDUP_CACHE.popleft()
    for g,c,hh,ts in DEDUP_CACHE:
        if g==guild_id and c==channel_id and hh==h and ts>=cutoff: return True
    DEDUP_CACHE.append((guild_id,channel_id,h,now)); return False

def short_hash(text): return hashlib.sha1(text.encode("utf-8","ignore")).hexdigest()

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    cfg = CFG.get("transfer",{})
    if not cfg.get("enabled"): return
    content = msg.content or ""
    for rule in cfg.get("rules", []):
        if msg.channel.id not in rule.get("from_channel_ids", []): continue
        if len(content)<rule.get("min_chars",0): continue
        if any(k in content for k in rule.get("ignore_if_contains", [])): continue
        if not any(k in content for k in rule.get("must_include", [])):
            import re
            if not any(re.search(p, content) for p in rule.get("regex_any", [])):
                continue
        h = short_hash(content[:2000])
        if recent_seen(msg.guild.id, msg.channel.id, h, 120): return
        to_ch = bot.get_channel(rule["to_channel_id"])
        if to_ch: await mirror_message(msg,to_ch)
        break
    await bot.process_commands(msg)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# --- Flask keepalive for Render Web Service ---
try:
    from flask import Flask, jsonify
except Exception as e:
    print("Flask not installed. Add Flask to requirements.txt if deploying to Render.")
    Flask = None

def run_keepalive():
    if Flask is None:
        print("Flask not available, skipping keepalive server.")
        return
    app = Flask("keepalive")
    @app.get("/")
    def root():
        return jsonify(status="ok"), 200
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN を環境変数に設定してください。")
    bot.run(TOKEN)
