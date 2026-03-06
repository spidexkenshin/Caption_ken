import json
import re
from pyrogram import Client, filters
from config import *

app = Client(
    "captionbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

DB_FILE = "db.json"

DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""


def load_db():
    with open(DB_FILE) as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


def extract(text):

    ep = re.search(r'episode\s*[-:]?\s*(\d+)', text, re.I)
    season = re.search(r'season\s*[-:]?\s*(\d+)', text, re.I)
    quality = re.search(r'(480p|720p|1080p|2160p|4k)', text, re.I)

    ep = int(ep.group(1)) if ep else 1
    season = int(season.group(1)) if season else 1
    quality = quality.group(1) if quality else "720p"

    ep = f"{ep:02}"
    season = f"{season:02}"

    return ep, season, quality


@app.on_message(filters.command("help"))
async def help(client, message):

    if message.from_user.id not in ADMINS:
        return

    await message.reply_text("""
Commands

/setcaption
/delcaption
/setcover
/help

Send video to auto rename caption
""")


# SET CAPTION
@app.on_message(filters.command("setcaption") & filters.reply)
async def setcaption(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    db["caption"] = message.reply_to_message.text

    save_db(db)

    await message.reply("✅ Caption Updated")


# DELETE CAPTION
@app.on_message(filters.command("delcaption"))
async def delcaption(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    db["caption"] = ""

    save_db(db)

    await message.reply("❌ Caption Deleted")


# SET COVER
@app.on_message(filters.command("setcover") & filters.reply)
async def setcover(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    db["cover"] = message.reply_to_message.photo.file_id

    save_db(db)

    await message.reply("✅ Cover Saved")


# VIDEO HANDLER
@app.on_message(filters.video)
async def rename(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    old_caption = message.caption or ""

    ep, season, quality = extract(old_caption)

    template = db["caption"] if db["caption"] else DEFAULT_CAPTION

    new_caption = template.format(
        anime_name="Unknown Anime",
        ep=ep,
        season=season,
        quality=quality
    )

    await message.copy(
        chat_id=message.chat.id,
        caption=new_caption
    )


print("Bot Running...")
app.run()
