import os
import re
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# ─── Config ───
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

ADMINS_FILE = "admins.json"
CAPTION_FILE = "caption.json"

# ─── Default Caption Template ───
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>

‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official

━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# ─── Helpers ───
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def get_admins():
    data = load_json(ADMINS_FILE, {"admins": [OWNER_ID]})
    if OWNER_ID not in data["admins"]:
        data["admins"].append(OWNER_ID)
        save_json(ADMINS_FILE, data)
    return data["admins"]

def is_admin(user_id):
    return user_id in get_admins()

def get_caption_template():
    data = load_json(CAPTION_FILE, {"caption": DEFAULT_CAPTION})
    return data["caption"]

def set_caption_template(caption):
    save_json(CAPTION_FILE, {"caption": caption})

def extract_info(caption):
    info = {"anime_name": "", "ep": "", "season": "01", "quality": "1080p"}
    if not caption:
        return info

    lines = caption.strip().split("\n")

    anime_match = re.search(r'(?:ᴀɴɪᴍᴇ|anime)[:\s]+(.+)', caption, re.IGNORECASE)
    if anime_match:
        info["anime_name"] = anime_match.group(1).strip()
    else:
        for line in lines:
            clean = line.strip()
            if clean and not re.match(r'^[━═─\-]+$', clean) and not any(k in clean.lower() for k in ['episode', 'season', 'quality', 'audio', 'powered', 'channel', 'ᴘᴏᴡᴇʀ', 'ᴍᴀɪɴ', '📟', '🎧', '📀', '⌬', '✻', '✾', '✵', '⧉', '➳']):
                if len(clean) < 60 and not clean.startswith('@'):
                    info["anime_name"] = clean
                    break

    ep_match = re.search(r'(?:episode|ep|ᴇᴘɪsᴏᴅᴇ|eᴘɪsᴏᴅᴇ)[:\s\-]*(\d+)', caption, re.IGNORECASE)
    if ep_match:
        info["ep"] = ep_match.group(1).strip()

    season_match = re.search(r'(?:season|s)[:\s\-]*(\d+)', caption, re.IGNORECASE)
    if season_match:
        info["season"] = season_match.group(1).strip()
    else:
        s_match = re.search(r'S(\d+)', caption)
        if s_match:
            info["season"] = s_match.group(1)
        s_match2 = re.search(r'S([¹²³⁴⁵⁶⁷⁸⁹⁰]+)', caption)
        if s_match2:
            superscript_map = {'¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','⁰':'0'}
            info["season"] = ''.join(superscript_map.get(c, c) for c in s_match2.group(1))

    quality_match = re.search(r'(\d{3,4}p|4[kK]|2160p)', caption, re.IGNORECASE)
    if quality_match:
        q = quality_match.group(1)
        if q.lower() in ['4k']:
            q = '2160p'
        info["quality"] = q

    return info

def get_quality_order(quality):
    order = {"480p": 0, "720p": 1, "1080p": 2, "1440p": 3, "2160p": 4, "4k": 4}
    return order.get(quality.lower(), 2)

# ─── Bot Init ───
app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You are not authorized.")
        return
    await message.reply("<blockquote>Jinda hu abhi..</blockquote>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    help_text = """<b>📖 Bot Commands:</b>

<b>Basic:</b>
/start - Check if bot is alive
/help - Show this help

<b>Caption:</b>
/setcaption - Set custom caption template
/getcaption - View current caption template
/resetcaption - Reset to default caption

<b>Rename:</b>
• Forward any video to rename its caption
/batch - Batch rename from channel
/sort - Sort and send videos by episode & quality

<b>Admin:</b>
/addadmin [user_id] - Add admin
/deladmin [user_id] - Remove admin
/admins - List all admins

<b>Placeholders:</b>
<code>{anime_name}</code> - Anime name
<code>{ep}</code> - Episode number
<code>{season}</code> - Season number
<code>{quality}</code> - Video quality
"""
    await message.reply(help_text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("setcaption") & filters.private)
async def setcaption_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    if len(message.text.split(None, 1)) < 2:
        await message.reply("Usage: /setcaption <your caption template>\n\nPlaceholders: {anime_name}, {ep}, {season}, {quality}")
        return
    new_caption = message.text.split(None, 1)[1]
    set_caption_template(new_caption)
    await message.reply("✅ Caption template updated!")

@app.on_message(filters.command("getcaption") & filters.private)
async def getcaption_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    caption = get_caption_template()
    await message.reply(f"<b>Current Caption Template:</b>\n\n<code>{caption}</code>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("resetcaption") & filters.private)
async def resetcaption_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    set_caption_template(DEFAULT_CAPTION)
    await message.reply("✅ Caption reset to default!")

@app.on_message(filters.command("addadmin") & filters.private)
async def addadmin_cmd(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ Only owner can add admins.")
        return
    try:
        new_admin = int(message.text.split()[1])
    except:
        await message.reply("Usage: /addadmin <user_id>")
        return
    admins = get_admins()
    if new_admin in admins:
        await message.reply("Already an admin.")
        return
    admins.append(new_admin)
    save_json(ADMINS_FILE, {"admins": admins})
    await message.reply(f"✅ Admin added: <code>{new_admin}</code>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("deladmin") & filters.private)
async def deladmin_cmd(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ Only owner can remove admins.")
        return
    try:
        del_admin = int(message.text.split()[1])
    except:
        await message.reply("Usage: /deladmin <user_id>")
        return
    if del_admin == OWNER_ID:
        await message.reply("❌ Cannot remove owner.")
        return
    admins = get_admins()
    if del_admin not in admins:
        await message.reply("Not an admin.")
        return
    admins.remove(del_admin)
    save_json(ADMINS_FILE, {"admins": admins})
    await message.reply(f"✅ Admin removed: <code>{del_admin}</code>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("admins") & filters.private)
async def admins_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    admins = get_admins()
    text = "<b>👥 Admin List:</b>\n\n"
    for a in admins:
        tag = "👑 Owner" if a == OWNER_ID else "🔹 Admin"
        text += f"{tag}: <code>{a}</code>\n"
    await message.reply(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.video & filters.private)
async def rename_video(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    status = await message.reply("⏳ Processing...")
    old_caption = message.caption or ""
    info = extract_info(old_caption)
    template = get_caption_template()
    new_caption = template.format(
        anime_name=info["anime_name"],
        ep=info["ep"],
        season=info["season"],
        quality=info["quality"]
    )
    try:
        await message.copy(
            chat_id=message.chat.id,
            caption=new_caption,
            parse_mode=ParseMode.HTML
        )
        await status.edit("✅ Done!")
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

@app.on_message(filters.command("batch") & filters.private)
async def batch_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: /batch <channel_username_or_id> [limit]\n\nExample: /batch @MyChannel 50")
        return
    channel = args[1]
    limit = int(args[2]) if len(args) > 2 else 100
    status = await message.reply(f"⏳ Fetching videos from {channel}...")
    videos = []
    try:
        async for msg in client.get_chat_history(channel, limit=limit):
            if msg.video:
                videos.append(msg)
    except Exception as e:
        await status.edit(f"❌ Error: {e}\n\nMake sure bot is admin in the channel.")
        return
    if not videos:
        await status.edit("No videos found.")
        return
    await status.edit(f"📦 Found {len(videos)} videos. Renaming...")
    template = get_caption_template()
    count = 0
    for vid in videos:
        old_caption = vid.caption or ""
        info = extract_info(old_caption)
        new_caption = template.format(
            anime_name=info["anime_name"],
            ep=info["ep"],
            season=info["season"],
            quality=info["quality"]
        )
        try:
            await vid.copy(
                chat_id=message.chat.id,
                caption=new_caption,
                parse_mode=ParseMode.HTML
            )
            count += 1
            await asyncio.sleep(1.5)
        except Exception as e:
            await message.reply(f"⚠️ Skip: {e}")
    await status.edit(f"✅ Done! Renamed {count}/{len(videos)} videos.")

@app.on_message(filters.command("sort") & filters.private)
async def sort_cmd(client, message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: /sort <channel_username_or_id> [limit]\n\nSorts by Episode → Quality (480p→720p→1080p→4k)")
        return
    channel = args[1]
    limit = int(args[2]) if len(args) > 2 else 100
    status = await message.reply(f"⏳ Fetching & sorting from {channel}...")
    videos = []
    try:
        async for msg in client.get_chat_history(channel, limit=limit):
            if msg.video:
                info = extract_info(msg.caption or "")
                videos.append({"msg": msg, "info": info})
    except Exception as e:
        await status.edit(f"❌ Error: {e}")
        return
    if not videos:
        await status.edit("No videos found.")
        return
    videos.sort(key=lambda x: (
        int(x["info"]["ep"]) if x["info"]["ep"].isdigit() else 999,
        get_quality_order(x["info"]["quality"])
    ))
    await status.edit(f"📦 Sorted {len(videos)} videos. Sending...")
    template = get_caption_template()
    count = 0
    for item in videos:
        info = item["info"]
        new_caption = template.format(
            anime_name=info["anime_name"],
            ep=info["ep"],
            season=info["season"],
            quality=info["quality"]
        )
        try:
            await item["msg"].copy(
                chat_id=message.chat.id,
                caption=new_caption,
                parse_mode=ParseMode.HTML
            )
            count += 1
            await asyncio.sleep(1.5)
        except Exception as e:
            await message.reply(f"⚠️ Skip: {e}")
    await status.edit(f"✅ Sorted & sent {count}/{len(videos)} videos.")

print("Bot is starting...")
app.run()
