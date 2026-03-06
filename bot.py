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

app = Client("KenshinSpeedBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Global Storage
video_queue = []
is_processing = False
target_sticker = None 

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

# --- Commands ---

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply("<blockquote>Jinda hu abhi....</blockquote>")

@app.on_message(filters.command("set_sticker") & filters.reply & filters.user(ADMIN_ID))
async def set_sticker_cmd(client, message: Message):
    global target_sticker
    if message.reply_to_message.sticker:
        target_sticker = message.reply_to_message.sticker.file_id
        await message.reply("✅ <b>Sticker Set! Ab har Ep ke baad yahi aayega.</b>")
    else:
        await message.reply("❌ Sticker ko reply karo bhai.")

@app.on_message(filters.command("cancel_queue") & filters.user(ADMIN_ID))
async def cancel_queue_cmd(client, message: Message):
    global video_queue, is_processing
    video_queue = []
    is_processing = False
    await message.reply("🛑 <b>Current Queue ko cancel kar diya gaya hai!</b>")

# --- Super Fast Processing Logic ---

async def process_queue(client, chat_id):
    global is_processing, video_queue, target_sticker
    is_processing = True
    
    # Sorting: Episode wise and then Quality wise
    video_queue.sort(key=lambda x: (x['ep_num'], x['q_rank']))
    
    status_msg = await client.send_message(chat_id, "⚡ <b>Speed Mode: Processing Started...</b>")

    last_ep = None
    if video_queue:
        last_ep = video_queue[0]['ep_num']

    for item in video_queue:
        # Agar beech mein kisi ne cancel kar diya ho
        if not is_processing:
            break

        msg = item['message']
        
        # Jab Episode badle tab sticker bhejo
        if last_ep is not None and item['ep_num'] != last_ep:
            if target_sticker:
                await client.send_sticker(chat_id, target_sticker)
                await asyncio.sleep(0.5)
            last_ep = item['ep_num']

        try:
            # Fast Copy using File ID
            file_id = msg.video.file_id if msg.video else msg.document.file_id
            
            await client.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=item['caption'],
                parse_mode=ParseMode.HTML,
                supports_streaming=True
            )
            
            # Instant Delete
            await msg.delete()
            # Minimal delay for max speed but avoiding flood
            await asyncio.sleep(0.7) 
            
        except Exception as e:
            print(f"Error: {e}")

    # Final Sticker after last episode
    if is_processing and target_sticker:
        await client.send_sticker(chat_id, target_sticker)

    if is_processing:
        await status_msg.edit("✅ <b>Kaam tamman! Saari videos bhej di gayi hain.</b>")
    
    video_queue = []
    is_processing = False

@app.on_message((filters.video | filters.document) & filters.private & filters.user(ADMIN_ID))
async def collector(client, message: Message):
    global video_queue
    original_caption = message.caption or ""
    
    # Optimized Extraction
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

    # Start processing if not already running
    if not is_processing:
        # Wait for 3 seconds to collect more forwarded files
        await asyncio.sleep(3)
        if not is_processing and video_queue:
            await process_queue(client, message.chat.id)

app.run()
