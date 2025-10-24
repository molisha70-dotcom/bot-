
import os, pytz, yaml, hashlib
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv
import discord
discord.opus = None
from discord.ext import commands
from discord import app_commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TZ = os.getenv("TZ", "Asia/Tokyo")
JST = pytz.timezone(TZ)

INTENTS = discord.Intents.default()
INTENTS.message_content = True  # 必須：メッセージ内容の取得

bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree

# ------- 設定ロード -------
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CFG = load_config()


@bot.event
async def setup_hook():
    """Ensure application commands are registered."""
    await bot.tree.sync()

# ------- 掲示板埋め込み生成 -------
async def mirror_message(msg: discord.Message, to_ch: discord.abc.Messageable):
    embed = discord.Embed(
        title="📌 転移されたお知らせ",
        description=(msg.content or "")[:4000],
        color=0x5865F2
    )
    embed.add_field(
        name="元の投稿",
        value=f"[ジャンプリンク]({msg.jump_url})\n投稿者：{msg.author.mention}／チャンネル：{msg.channel.mention}",
        inline=False
    )
    # 画像1枚だけ拾う
    if msg.attachments:
        a = msg.attachments[0]
        if a.content_type and a.content_type.startswith("image/"):
            embed.set_image(url=a.url)
    await to_ch.send(embed=embed)

# ------- デュープ防止 -------
DEDUP_CACHE = deque(maxlen=500)  # (guild_id, channel_id, hash, ts)
def recent_seen(guild_id, channel_id, h, window_minutes: int) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=window_minutes)
    while DEDUP_CACHE and DEDUP_CACHE[0][3] < cutoff:
        DEDUP_CACHE.popleft()
    for g, c, hh, ts in DEDUP_CACHE:
        if g == guild_id and c == channel_id and hh == h and ts >= cutoff:
            return True
    DEDUP_CACHE.append((guild_id, channel_id, h, now))
    return False

def short_hash(text: str, n: int = 2000) -> str:
    return hashlib.sha1((text[:n]).encode("utf-8", errors="ignore")).hexdigest()

# ------- Auto-mirror -------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    cfg = CFG.get("transfer", {})
    if not cfg.get("enabled"):
        return

    content = message.content or ""

    for rule in cfg.get("rules", []):
        if message.channel.id not in rule.get("from_channel_ids", []):
            continue

        # 判定：必須ワード or 正規表現のどちらか
        must = rule.get("must_include", [])
        regex_any = rule.get("regex_any", [])
        has_must = any(k in content for k in must) if must else False
        if not has_must:
            import re
            has_regex = any(re.search(p, content) for p in regex_any)
            if not has_regex:
                continue

        if any(k in content for k in rule.get("ignore_if_contains", [])):
            continue
        if len(content) < int(rule.get("min_chars", 0)):
            continue

        # 重複防止
        h = short_hash(content, n=int(cfg.get("dedup", {}).get("hash_length", 2000)))
        window = int(cfg.get("dedup", {}).get("window_minutes", 120))
        if recent_seen(message.guild.id, message.channel.id, h, window_minutes=window):
            continue

        to_ch = bot.get_channel(int(rule["to_channel_id"]))
        if to_ch:
            await mirror_message(message, to_ch)
        break

    await bot.process_commands(message)

# ------- 便利コマンド -------
@tree.command(name="reload_config", description="config.yaml を再読み込みします")
async def reload_config(interaction: discord.Interaction):
    global CFG
    CFG = load_config()
    await interaction.response.send_message("設定を再読み込みしました。", ephemeral=True)

@tree.command(name="announce", description="テンプレ掲示板を投稿/プレビュー")
async def announce(interaction: discord.Interaction, action: str, template: str):
    try:
        t = CFG["templates"][template]
    except KeyError:
        await interaction.response.send_message(f"テンプレ '{template}' が見つかりません。", ephemeral=True)
        return

    title = f'{CFG.get("brand_emoji","")} {t["title"]}'
    embed = discord.Embed(
        title=title,
        description=t.get("header",""),
        color=t.get("color", 0x5865F2)
    )
    embed.set_author(name=CFG.get("server_name",""))
    for block in CFG.get("blocks", []):
        lines = []
        for it in block.get("items", []):
            tag = it.get("tag","")
            sched = it.get("schedule_text","")
            lines.append(f"• **{tag}**\n{sched}")
        value = "\n\n".join(lines) if lines else "（情報なし）"
        embed.add_field(name=f"▮ {block['title']}", value=value, inline=False)

    now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    embed.set_footer(text=f"自動生成｜{now} {TZ}")

    if action == "preview":
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # 投稿先は config の to_channel_id を流用（単純化）
        to_ch_id = CFG["transfer"]["rules"][0]["to_channel_id"]
        ch = interaction.client.get_channel(int(to_ch_id))
        if not ch:
            await interaction.response.send_message("投稿先チャンネルが見つかりません。", ephemeral=True)
            return
        await ch.send(embed=embed)
        await interaction.response.send_message("投稿しました。", ephemeral=True)

# ------- 起動エクスポート -------
def run_bot():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN が未設定です。.env か Render の環境変数で設定してください。")

    bot.run(TOKEN)
