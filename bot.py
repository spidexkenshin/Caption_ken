import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------- ENV LOAD SAFELY ---------------- #

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_IDS = os.getenv("ADMIN_IDS")

if not API_ID or not API_HASH or not BOT_TOKEN or not MONGO_URI or not ADMIN_IDS:
    raise ValueError("❌ One or more environment variables are missing!")

API_ID = int(API_ID)
ADMIN_IDS = list(map(int, ADMIN_IDS.split(",")))

# ---------------- DEFAULT CAPTION ---------------- #

DEFAULT_CAPTION = """<b><blockquote> ✨ {anime} ✨</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : {audio} | Official🎙️
━━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join: [@KENSHIN_ANIME & MANWHA_VERSE]</blockquote>
━━━━━━━━━━━━━━━━━━━━━━</b>"""

# ---------------- APP INIT ---------------- #

app = Client(
    "caption-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["caption_bot"]
users = db["users"]
admins_db = db["admins"]

# ---------------- ADMIN CHECK ---------------- #

async def is_admin(user_id):
    if user_id in ADMIN_IDS:
        return True
    admin = await admins_db.find_one({"user_id": user_id})
    return bool(admin)

# ---------------- START ---------------- #

@app.on_message(filters.command("start"))
async def start(client, message):
    if not await is_admin(message.from_user.id):
        return await message.reply_text("❌ Only Admin Can Use This Bot")
    await message.reply_text("🔥 Caption Changer Bot Ready!")

# ---------------- SET CAPTION ---------------- #

@app.on_message(filters.command("setcaption"))
async def set_caption(client, message):
    if not await is_admin(message.from_user.id):
        return

    text = message.text.split(None, 1)
    if len(text) < 2:
        return await message.reply_text("Send caption after command")

    await users.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"caption": text[1]}},
        upsert=True
    )

    await message.reply_text("✅ Custom Caption Saved!")

# ---------------- VIDEO HANDLER ---------------- #

@app.on_message(filters.video)
async def change_caption(client, message: Message):
    if not await is_admin(message.from_user.id):
        return

    user = await users.find_one({"user_id": message.from_user.id})
    caption_template = user["caption"] if user else DEFAULT_CAPTION

    original_caption = message.caption or ""

    anime = re.search(r"Anime[:\s]+(.+)", original_caption, re.IGNORECASE)
    ep = re.search(r"Episode[:\s]+(\d+)", original_caption, re.IGNORECASE)
    season = re.search(r"Season[:\s]+(\d+)", original_caption, re.IGNORECASE)
    quality = re.search(r"Quality[:\s]+(\S+)", original_caption, re.IGNORECASE)
    audio = re.search(r"Audio[:\s]+(.+)", original_caption, re.IGNORECASE)

    data = {
        "anime": anime.group(1) if anime else "Unknown",
        "ep": ep.group(1) if ep else "00",
        "season": season.group(1) if season else "01",
        "quality": quality.group(1) if quality else "1080p",
        "audio": audio.group(1) if audio else "Hindi"
    }

    new_caption = caption_template.format(**data)

    await client.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.id,
        caption=new_caption,
        parse_mode="html"
    )

app.run()
