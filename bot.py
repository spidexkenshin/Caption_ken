import re
from pyrogram import Client, filters
from config import *

app = Client(
    "captionbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

DEFAULT_CAPTION = """<b><blockquote>💫 {anime} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : {audio}
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""


# -------- EXTRACT DATA FROM CAPTION --------

def extract_data(text):

    anime = re.search(r'Anime:\s*(.*)', text, re.I)
    season = re.search(r'Season:\s*(\d+)', text, re.I)
    episode = re.search(r'Episode:\s*(\d+)', text, re.I)
    quality = re.search(r'(480p|720p|1080p|2160p|4k)', text, re.I)
    audio = re.search(r'Audio:\s*(.*)', text, re.I)

    anime = anime.group(1).strip() if anime else "Unknown Anime"
    season = int(season.group(1)) if season else 1
    episode = int(episode.group(1)) if episode else 1
    quality = quality.group(1) if quality else "1080p"
    audio = audio.group(1).strip() if audio else "Hindi"

    season = f"{season:02}"
    episode = f"{episode:02}"

    return anime, season, episode, quality, audio


# -------- QUALITY SORT ORDER --------

def quality_sort(q):

    order = {
        "480p": 1,
        "720p": 2,
        "1080p": 3,
        "2160p": 4,
        "4k": 4
    }

    return order.get(q.lower(), 5)


# -------- START MESSAGE --------

@app.on_message(filters.command("start"))
async def start(client, message):

    await message.reply_text(
        "<b><blockquote>Jinda hu abhi... </blockquote></b>"
    )


# -------- VIDEO HANDLER --------

@app.on_message(filters.video)
async def rename_video(client, message):

    old_caption = message.caption or ""

    anime, season, ep, quality, audio = extract_data(old_caption)

    new_caption = DEFAULT_CAPTION.format(
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
