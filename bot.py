
import os, pytz, yaml, hashlib
from collections import deque, defaultdict
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
import discord
discord.opus = None
from discord.ext import commands, tasks
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

SUMMARY_INTERVAL_MINUTES = int(os.getenv("SUMMARY_INTERVAL_MINUTES", "10"))

PendingKey = Tuple[int, int]
PendingEntry = Dict[str, str]
PENDING_MESSAGES: Dict[PendingKey, List[PendingEntry]] = defaultdict(list)

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

def queue_pending_message(message: discord.Message, to_channel_id: int, rule_name: str):
    content = (message.content or "").strip()
    snippet = content[:180] + ("…" if len(content) > 180 else "")
    image_url = None
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            image_url = attachment.url
            break

    entry: PendingEntry = {
        "author": message.author.mention,
        "channel": message.channel.mention,
        "jump_url": message.jump_url,
        "snippet": snippet or "（本文なし）",
        "rule": rule_name,
    }
    if image_url:
        entry["image_url"] = image_url

    key = (message.guild.id, to_channel_id)
    PENDING_MESSAGES[key].append(entry)


def build_summary_embed(entries: List[PendingEntry]) -> discord.Embed:
    title = "📬 まとめ転送"
    first_rule = entries[0].get("rule", "")
    if first_rule:
        title += f"｜{first_rule}"

    embed = discord.Embed(
        title=title,
        description="",
        color=0x2F3136,
    )

    lines = []
    image_url = None
    for entry in entries:
        line = (
            f"• {entry['author']} （{entry['channel']}）\n"
            f"{entry['snippet']}\n"
            f"[ジャンプリンク]({entry['jump_url']})"
        )
        lines.append(line)
        if not image_url and entry.get("image_url"):
            image_url = entry["image_url"]

    description = "\n\n".join(lines)
    if len(description) > 4000:
        description = description[:3997] + "…"

    embed.description = description

    now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    embed.set_footer(text=f"まとめ投稿｜{now} {TZ}")

    if image_url:
        embed.set_image(url=image_url)

    return embed


@tasks.loop(minutes=SUMMARY_INTERVAL_MINUTES)
async def flush_pending_messages():
    if not PENDING_MESSAGES:
        return

    for key, entries in list(PENDING_MESSAGES.items()):
        if not entries:
            continue

        _, to_channel_id = key
        channel = bot.get_channel(to_channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(to_channel_id)
            except discord.NotFound:
                print(f"Summary target channel {to_channel_id} was not found. Discarding queued entries.")
                PENDING_MESSAGES.pop(key, None)
                continue
            except discord.Forbidden:
                print(f"Missing permissions to access summary target channel {to_channel_id}. Discarding queued entries.")
                PENDING_MESSAGES.pop(key, None)
                continue
            except discord.HTTPException as exc:
                # Keep the entries so we can retry on the next loop iteration.
                print(f"Failed to fetch summary target channel {to_channel_id}: {exc}")
                continue

        embed = build_summary_embed(entries)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            print(f"Failed to send summary to {to_channel_id}: {exc}")
        finally:
            PENDING_MESSAGES.pop(key, None)

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
        dedup_cfg = cfg.get("dedup") or CFG.get("dedup", {})
        hash_len = int(dedup_cfg.get("hash_length", 2000))
        window = int(dedup_cfg.get("window_minutes", 120))
        h = short_hash(content, n=hash_len)
        if recent_seen(message.guild.id, message.channel.id, h, window_minutes=window):
            continue

        to_ch_id = int(rule["to_channel_id"])
        queue_pending_message(message, to_ch_id, rule.get("name", ""))
        break

    await bot.process_commands(message)

@bot.event
async def on_ready():
    if not getattr(bot, "_synced", False):
        await bot.tree.sync()
        bot._synced = True
    if not flush_pending_messages.is_running():
        flush_pending_messages.start()
    print(f"Bot logged in as {bot.user} ({bot.user.id})")

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

    async def _runner():
        await bot.login(TOKEN)
        await bot.tree.sync()
        await bot.connect(reconnect=True)

    import asyncio
    asyncio.run(_runner())
