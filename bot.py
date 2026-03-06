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

app = Client("CaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Global Storage
video_queue = []
is_processing = False
target_sticker = None # Sticker ID store karne ke liye

CAPTION_TEMPLATE = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

def get_quality_rank(q_str):
    ranks = {"480p": 1, "720p": 2, "1080p": 3, "4k": 4, "2160p": 5}
    return ranks.get(q_str.lower(), 0)

# --- Sticker Setting Command ---
@app.on_message(filters.command("set_sticker") & filters.reply & filters.user(ADMIN_ID))
async def set_sticker_cmd(client, message: Message):
    global target_sticker
    if message.reply_to_message.sticker:
        target_sticker = message.reply_to_message.sticker.file_id
        await message.reply("✅ <b>Bhai sticker set ho gaya! Ab har Episode ke baad yahi bhejunga.</b>")
    else:
        await message.reply("❌ <b>Bhai kisi Sticker ko reply karke ye command bhejo!</b>")

# --- Processing Logic ---
async def process_queue(client, chat_id):
    global is_processing, video_queue, target_sticker
    is_processing = True
    
    # 1. Sorting: Pehle Episode, phir Quality
    video_queue.sort(key=lambda x: (x['ep_num'], x['q_rank']))
    
    status_msg = await client.send_message(chat_id, f"🚀 <b>Found {len(video_queue)} files. Sending with Stickers...</b>")

    last_ep = None
    if video_queue:
        last_ep = video_queue[0]['ep_num']

    for i, item in enumerate(video_queue):
        msg = item['message']
        
        # Check if Episode changed (Sticker bhejne ke liye)
        if last_ep is not None and item['ep_num'] != last_ep:
            if target_sticker:
                await client.send_sticker(chat_id, target_sticker)
                await asyncio.sleep(1)
            last_ep = item['ep_num']

        try:
            # Send Video with Instant Rename
            await client.send_video(
                chat_id=chat_id,
                video=msg.video.file_id if msg.video else msg.document.file_id,
                caption=item['caption'],
                file_name=item['new_file_name'], 
                parse_mode=ParseMode.HTML,
                supports_streaming=True
            )
            
            # Original Delete
            await msg.delete()
            await asyncio.sleep(1.5) 
            
        except Exception as e:
            print(f"Error: {e}")

    # Last episode ke baad final sticker
    if target_sticker:
        await client.send_sticker(chat_id, target_sticker)

    await status_msg.edit("✅ <b>Kaam ho gaya bhai! Stickers ke sath saari videos bhej di.</b>")
    video_queue = []
    is_processing = False

@app.on_message((filters.video | filters.document) & filters.private & filters.user(ADMIN_ID))
async def collector(client, message: Message):
    original_caption = message.caption or ""
    
    # Extraction
    ep_match = re.search(r"(?i)(?:Episode|Ep)[\s\-:]*(\d+)", original_caption)
    ep_num = int(ep_match.group(1)) if ep_match else 0
    ep_str = str(ep_num).zfill(2)

    quality_match = re.search(r"(?i)(1080p|720p|480p|360p|4K|2160p)", original_caption)
    quality = quality_match.group(1) if quality_match else "Unknown"
    
    anime_match = re.search(r"(?i)(?:ᴀɴɪᴍᴇ|Anime|Name)[\s\-:]*(.+)", original_caption)
    anime_name = anime_match.group(1).strip() if anime_match else "Anime"

    # File Name as per your request
    new_file_name = f"For more join: [@KENSHIN_ANIME].mp4"

    new_caption = CAPTION_TEMPLATE.format(
        anime_name=anime_name, ep=ep_str, season="01", quality=quality
    )

    video_queue.append({
        'message': message,
        'ep_num': ep_num,
        'q_rank': get_quality_rank(quality),
        'caption': new_caption,
        'new_file_name': new_file_name
    })

    if not is_processing:
        await asyncio.sleep(5) # Thoda extra time for heavy forwarding
        if not is_processing and video_queue:
            await process_queue(client, message.chat.id)

app.run()
