import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# Config
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

app = Client("KenshinBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Global Storage
video_queue = []
is_processing = False
target_sticker = None
target_cover = None # Thumbnail storage

CAPTION_TEMPLATE = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

HELP_TEXT = """🚀 <b>Detailed Guide for Admin:</b>

1. <b>Start:</b> /start se check karein bot on hai.
2. <b>Set Sticker:</b> Kisi sticker ko reply karke <code>/set_sticker</code> likhein. Ye har episode ke baad aayega.
3. <b>Set Cover:</b> Kisi photo ko reply karke <code>/set_cover</code> likhein. Ye har video ka thumbnail ban jayega.
4. <b>Processing:</b> Bas videos forward karein, bot auto-sort, rename, aur clean-up kar dega.
"""

def get_quality_rank(q_str):
    ranks = {"480p": 1, "720p": 2, "1080p": 3, "4k": 4, "2160p": 5}
    return ranks.get(q_str.lower(), 0)

# --- Commands ---

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply("<blockquote>Jinda hu abhi....</blockquote>")

@app.on_message(filters.command("help") & filters.private & filters.user(ADMIN_ID))
async def help_cmd(client, message: Message):
    await message.reply(HELP_TEXT)

@app.on_message(filters.command("set_sticker") & filters.reply & filters.user(ADMIN_ID))
async def set_sticker_cmd(client, message: Message):
    global target_sticker
    if message.reply_to_message.sticker:
        target_sticker = message.reply_to_message.sticker.file_id
        await message.reply("✅ <b>Sticker Set! Ab har Ep ke baad maze lega.</b>")
    else:
        await message.reply("❌ Bhai Sticker ko reply karo.")

@app.on_message(filters.command("set_cover") & filters.reply & filters.user(ADMIN_ID))
async def set_cover_cmd(client, message: Message):
    global target_cover
    if message.reply_to_message.photo:
        # Download photo for thumbnail (only once)
        target_cover = await client.download_media(message.reply_to_message.photo)
        await message.reply("🖼 <b>Cover Set! Ab har video professional dikhegi.</b>")
    else:
        await message.reply("❌ Bhai Photo ko reply karo.")

# --- Fast Processing Logic ---

async def process_queue(client, chat_id):
    global is_processing, video_queue, target_sticker, target_cover
    is_processing = True
    
    video_queue.sort(key=lambda x: (x['ep_num'], x['q_rank']))
    status_msg = await client.send_message(chat_id, "⚡ <b>Speed mode active... Processing!</b>")

    last_ep = None
    if video_queue:
        last_ep = video_queue[0]['ep_num']

    for item in video_queue:
        msg = item['message']
        
        # Sticker between episodes
        if last_ep is not None and item['ep_num'] != last_ep:
            if target_sticker:
                await client.send_sticker(chat_id, target_sticker)
            last_ep = item['ep_num']

        try:
            # File ID for instant copy
            f_id = msg.video.file_id if msg.video else msg.document.file_id
            
            # Send Video (Rename + Cover + Caption)
            await client.send_video(
                chat_id=chat_id,
                video=f_id,
                caption=item['caption'],
                file_name="For more join: [@KENSHIN_ANIME].mp4", # Fixed Rename
                thumb=target_cover, # Custom Cover
                parse_mode=ParseMode.HTML,
                supports_streaming=True
            )
            
            await msg.delete()
            await asyncio.sleep(0.8) # Ultra Fast delay
            
        except Exception as e:
            print(f"Error: {e}")

    if target_sticker:
        await client.send_sticker(chat_id, target_sticker)

    await status_msg.edit("✅ <b>All done! Fast and Clean.</b>")
    video_queue = []
    is_processing = False

@app.on_message((filters.video | filters.document) & filters.private & filters.user(ADMIN_ID))
async def collector(client, message: Message):
    original_caption = message.caption or ""
    
    # Fast Extraction
    ep_match = re.search(r"(?i)(?:Episode|Ep)[\s\-:]*(\d+)", original_caption)
    ep_num = int(ep_match.group(1)) if ep_match else 0
    
    quality_match = re.search(r"(?i)(1080p|720p|480p|360p|4K|2160p)", original_caption)
    quality = quality_match.group(1) if quality_match else "HD"
    
    anime_match = re.search(r"(?i)(?:ᴀɴɪᴍᴇ|Anime|Name)[\s\-:]*(.+)", original_caption)
    anime_name = anime_match.group(1).split('\n')[0].strip() if anime_match else "Anime"

    new_caption = CAPTION_TEMPLATE.format(
        anime_name=anime_name, ep=str(ep_num).zfill(2), season="01", quality=quality
    )

    video_queue.append({
        'message': message,
        'ep_num': ep_num,
        'q_rank': get_quality_rank(quality),
        'caption': new_caption
    })

    if not is_processing:
        await asyncio.sleep(3) # Collecting time
        if not is_processing:
            await process_queue(client, message.chat.id)

app.run()
