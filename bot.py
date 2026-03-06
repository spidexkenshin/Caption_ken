import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# Environment Variables se data nikalna
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Pyrogram Client Setup
app = Client("CaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Tumhara Default Caption Template
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.reply("<b><blockquote> Jinda hu abhi.. </blockquote></b>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    help_text = "Bhai, bas apni video yaha send/forward kar. Mai automatically purane caption se data nikal kar naya format laga dunga."
    await message.reply(help_text)

@app.on_message((filters.video | filters.document) & filters.private)
async def change_caption(client, message: Message):
    # Sirf Admin allow hai
    if message.from_user.id != ADMIN_ID:
        return

    original_caption = message.caption or message.text or ""
    
    # 1. Episode Extract karna (e.g. Episode - 24 ya Episode: 07)
    ep_match = re.search(r"(?i)(?:Episode|Ep)[\s\-:]*(\d+)", original_caption)
    ep = ep_match.group(1) if ep_match else "Unknown"

    # 2. Season Extract karna (e.g. S01 ya Season: 01)
    season_match = re.search(r"(?i)(?:Season|S)[\s\-:]*(\d+)", original_caption)
    season = season_match.group(1) if season_match else "01"

    # 3. Quality Extract karna (e.g. 1080p, 720p, 4k)
    quality_match = re.search(r"(?i)(1080p|720p|480p|360p|4K|2160p)", original_caption)
    quality = quality_match.group(1) if quality_match else "Unknown"

    # 4. Anime Name Extract karna (e.g. ᴀɴɪᴍᴇ: To Be Hero X)
    anime_match = re.search(r"(?i)(?:ᴀɴɪᴍᴇ|Anime|Name)[\s\-:]*(.+)", original_caption)
    if anime_match:
        anime_name = anime_match.group(1).strip()
    else:
        # Agar purane caption me Anime name nahi hai (jaise tumhare 1st example me)
        anime_name = "Unknown Anime"

    # Naya caption format karna
    new_caption = DEFAULT_CAPTION.format(
        anime_name=anime_name,
        ep=ep,
        season=season,
        quality=quality
    )

    # Video ko naye caption ke sath bhej do (Copy message is safe)
    await message.copy(
        chat_id=message.chat.id,
        caption=new_caption,
        parse_mode=ParseMode.HTML
    )

app.run()
