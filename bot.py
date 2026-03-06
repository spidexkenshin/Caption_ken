import re
import json
from pyrogram import Client, filters
from config import *

app = Client(
    "captionbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

DB_FILE = "db.json"

DEFAULT_CAPTION = """<b><blockquote>💫 {anime} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : {audio}
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""


# ---------- DATABASE ----------

def load_db():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except:
        return {"caption": "", "cover": ""}


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------- EXTRACT DATA ----------

def extract_data(text):

    anime = re.search(r'Anime:\s*(.*)', text, re.I)
    season = re.search(r'Season:\s*(\d+)', text, re.I)
    episode = re.search(r'Episode:\s*(\d+)', text, re.I)
    quality = re.search(r'Quality:\s*(\S+)', text, re.I)
    audio = re.search(r'Audio:\s*(.*)', text, re.I)

    anime = anime.group(1).strip() if anime else "Unknown Anime"

    season = int(season.group(1)) if season else 1
    episode = int(episode.group(1)) if episode else 1

    quality = quality.group(1) if quality else "1080p"
    audio = audio.group(1).strip() if audio else "Hindi"

    season = f"{season:02}"
    episode = f"{episode:02}"

    return anime, season, episode, quality, audio


# ---------- START ----------

@app.on_message(filters.command("start"))
async def start(client, message):

    if message.from_user.id not in ADMINS:
        return

    await message.reply_text(
        "<b><blockquote>Jinda hu abhi... </blockquote></b>"
    )


# ---------- HELP ----------

@app.on_message(filters.command("help"))
async def help_cmd(client, message):

    if message.from_user.id not in ADMINS:
        return

    await message.reply_text(
"""
Commands

/setcaption (reply)
Set custom caption

/delcaption
Delete caption

/help
Show commands
"""
)


# ---------- SET CAPTION ----------

@app.on_message(filters.command("setcaption") & filters.reply)
async def setcaption(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    db["caption"] = message.reply_to_message.text

    save_db(db)

    await message.reply("✅ Caption Updated")


# ---------- DELETE CAPTION ----------

@app.on_message(filters.command("delcaption"))
async def delcaption(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    db["caption"] = ""

    save_db(db)

    await message.reply("❌ Caption Deleted")


# ---------- VIDEO HANDLER ----------

@app.on_message(filters.video)
async def rename_video(client, message):

    if message.from_user.id not in ADMINS:
        return

    db = load_db()

    old_caption = message.caption or ""

    anime, season, ep, quality, audio = extract_data(old_caption)

    template = db["caption"] if db["caption"] else DEFAULT_CAPTION

    new_caption = template.format(
        anime=anime,
        season=season,
        ep=ep,
        quality=quality,
        audio=audio
    )

    await message.copy(
        chat_id=message.chat.id,
        caption=new_caption
    )


print("Bot Running...")
app.run()
