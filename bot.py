import os
import re
import asyncio
import time
from collections import defaultdict
from pyrofork import Client, filters
from pyrofork.types import Message
from pyrofork.enums import ParseMode

# ========== CONFIGURATION ==========
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.environ.get("ADMIN_IDS", "").split())) if os.environ.get("ADMIN_IDS") else []

# Default Caption Template
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>

‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official

━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# Global storage
user_captions = {}
user_rename_sessions = {}
video_queues = defaultdict(list)  # user_id -> list of videos to process
processing_status = {}  # user_id -> processing status

# Quality order for sorting
QUALITY_ORDER = {
    '144p': 1, '240p': 2, '360p': 3, '480p': 4,
    '720p': 5, '1080p': 6, '1440p': 7, '2k': 7,
    '4k': 8, '2160p': 8, '8k': 9, '4320p': 9
}

# ========== BOT INITIALIZATION ==========
app = Client(
    "caption_changer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=200,
    max_concurrent_transmissions=50
)

# ========== HELPER FUNCTIONS ==========

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def extract_info_from_caption(caption: str) -> dict:
    info = {'anime_name': '', 'ep': 'N/A', 'season': 'S01', 'quality': '1080p'}
    if not caption:
        return info
    
    # Episode patterns
    ep_patterns = [
        r'[Ee]pisode\s*[-:]?\s*(\d+)',
        r'[Ee]pisode\s*[:=]\s*(\d+)',
        r'[Ee]p\s*(\d+)',
        r'[#\s](\d+)[\s\n]'
    ]
    for pattern in ep_patterns:
        match = re.search(pattern, caption)
        if match:
            info['ep'] = match.group(1)
            break
    
    # Season patterns
    season_match = re.search(r'[Ss]0?(\d+)|[Ss]eason\s*(\d+)', caption)
    if season_match:
        season_num = season_match.group(1) or season_match.group(2)
        info['season'] = f"S0{season_num}"
    
    # Quality patterns
    q_patterns = [r'(\d{3,4}p)', r'4[Kk]', r'2[Kk]', r'8[Kk]']
    for pattern in q_patterns:
        q_match = re.search(pattern, caption, re.IGNORECASE)
        if q_match:
            info['quality'] = q_match.group(0).lower()
            break
    
    # Anime name extraction
    anime_patterns = [
        r'[🎬📟🎥]\s*[Aa]nime[:\-]?\s*([^\n]+)',
        r'[Nn]ame[:\-]?\s*([^\n]+)',
    ]
    for pattern in anime_patterns:
        anime_match = re.search(pattern, caption)
        if anime_match:
            info['anime_name'] = anime_match.group(1).strip()
            break
    
    # If no anime name found, try first clean line
    if not info['anime_name']:
        lines = caption.strip().split('\n')
        for line in lines[:2]:
            clean = re.sub(r'[^\w\s\-]', '', line).strip()
            if clean and len(clean) > 2 and not any(x in clean.lower() for x in ['episode', 'season', 'quality']):
                info['anime_name'] = clean
                break
    
    return info

def get_quality_priority(quality: str) -> int:
    q = quality.lower().replace(' ', '')
    for key, value in QUALITY_ORDER.items():
        if key in q:
            return value
    return 99

def extract_info_from_filename(filename: str) -> dict:
    info = {'anime_name': '', 'ep': 'N/A', 'season': 'S01', 'quality': '1080p'}
    name = os.path.splitext(filename)[0]
    
    # Episode
    ep_match = re.search(r'[Ee]p?(\d+)|[Ee]pisode\s*(\d+)', name, re.IGNORECASE)
    if ep_match:
        info['ep'] = ep_match.group(1) or ep_match.group(2)
    
    # Season
    season_match = re.search(r'[Ss]0?(\d+)|[Ss]eason\s*(\d+)', name, re.IGNORECASE)
    if season_match:
        info['season'] = f"S0{season_match.group(1) or season_match.group(2)}"
    
    # Quality
    q_match = re.search(r'(\d{3,4}p|4[Kk]|2[Kk]|8[Kk])', name, re.IGNORECASE)
    if q_match:
        info['quality'] = q_match.group(0).lower()
    
    # Anime name
    name_clean = re.sub(r'[._\-]', ' ', name)
    parts = re.split(r'[Ss]\d+|[Ee]p?\d+', name_clean, flags=re.IGNORECASE)
    if parts and parts[0].strip():
        info['anime_name'] = parts[0].strip()
    
    return info

def parse_caption_template(template: str, info: dict) -> str:
    try:
        return template.format(**info)
    except:
        return DEFAULT_CAPTION.format(**info)

# ========== AUTO PROCESSING QUEUE ==========

async def process_video_queue(user_id: int, chat_id: int):
    """Process queued videos for a user"""
    if processing_status.get(user_id, False):
        return
    
    processing_status[user_id] = True
    queue = video_queues[user_id]
    
    if not queue:
        processing_status[user_id] = False
        return
    
    # Send processing message
    status_msg = await app.send_message(
        chat_id,
        f"<b>⏳ Processing {len(queue)} videos...</b>\n<i>Sorting and renaming captions...</i>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Get user caption template
        caption_template = user_captions.get(user_id, DEFAULT_CAPTION)
        
        # Process all videos and extract info
        processed_videos = []
        
        for item in queue:
            msg = item['message']
            info = None
            
            # Try caption first
            if msg.caption:
                info = extract_info_from_caption(msg.caption)
            
            # Try filename
            if not info or not info['anime_name']:
                filename = ""
                if msg.video and msg.video.file_name:
                    filename = msg.video.file_name
                elif msg.document and msg.document.file_name:
                    filename = msg.document.file_name
                
                if filename:
                    file_info = extract_info_from_filename(filename)
                    if info:
                        file_info.update({k: v for k, v in info.items() if v and v != 'N/A'})
                    info = file_info
            
            if not info:
                info = {'anime_name': 'Unknown Anime', 'ep': '01', 'season': 'S01', 'quality': '1080p'}
            
            # Generate new caption
            new_caption = parse_caption_template(caption_template, info)
            
            processed_videos.append({
                'msg': msg,
                'caption': new_caption,
                'ep_num': int(info['ep']) if str(info['ep']).isdigit() else 999,
                'quality_priority': get_quality_priority(info['quality']),
                'info': info
            })
        
        # Sort: Episode first, then Quality
        processed_videos.sort(key=lambda x: (x['ep_num'], x['quality_priority']))
        
        # Clear queue
        video_queues[user_id] = []
        
        # Send sorted videos
        total = len(processed_videos)
        success = 0
        failed = 0
        
        await status_msg.edit_text(
            f"<b>⚡ Sending {total} videos...</b>\n"
            f"<i>Sorted by Episode -> Quality</i>",
            parse_mode=ParseMode.HTML
        )
        
        for idx, item in enumerate(processed_videos, 1):
            try:
                msg = item['msg']
                caption = item['caption']
                
                if msg.video:
                    await app.send_video(
                        chat_id=chat_id,
                        video=msg.video.file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        duration=msg.video.duration,
                        width=msg.video.width,
                        height=msg.video.height,
                        thumb=msg.video.thumbs[0].file_id if msg.video.thumbs else None,
                        supports_streaming=True
                    )
                elif msg.document:
                    await app.send_document(
                        chat_id=chat_id,
                        document=msg.document.file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        thumb=msg.document.thumbs[0].file_id if msg.document.thumbs else None
                    )
                elif msg.animation:
                    await app.send_animation(
                        chat_id=chat_id,
                        animation=msg.animation.file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                
                success += 1
                
                # Update progress every 10 videos
                if idx % 10 == 0 or idx == total:
                    await status_msg.edit_text(
                        f"<b>⏳ Progress: {idx}/{total}</b>\n"
                        f"✅ Sent: {success}\n"
                        f"❌ Failed: {failed}\n\n"
                        f"<i>Sorting: Ep {item['info']['ep']} | {item['info']['quality']}</i>",
                        parse_mode=ParseMode.HTML
                    )
                
                # Small delay to prevent flood
                await asyncio.sleep(0.3)
                
            except Exception as e:
                failed += 1
                continue
        
        # Final message
        await status_msg.edit_text(
            f"<b>🎉 Complete! Processed {total} videos</b>\n\n"
            f"✅ <b>Success:</b> {success}\n"
            f"❌ <b>Failed:</b> {failed}\n\n"
            f"<i>✓ Sorted by Episode Number\n"
            f"✓ Sorted by Quality (480p→720p→1080p→4K)\n"
            f"✓ Captions renamed with template</i>",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await status_msg.edit_text(f"<b>❌ Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
    
    finally:
        processing_status[user_id] = False

# ========== COMMAND HANDLERS ==========

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply("⚠️ You are not authorized to use this bot.")
    
    await message.reply(
        "<blockquote>Jinda hu abhi..</blockquote>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    help_text = """<b>📋 Available Commands:</b>

<code>/start</code> - Check bot status
<code>/help</code> - Show this help
<code>/setcaption</code> - Set custom caption
<code>/viewcaption</code> - View current caption
<code>/resetcaption</code> - Reset to default
<code>/process</code> - Process queued videos manually
<code>/clear</code> - Clear video queue

<b>🚀 Auto Features:</b>
• Send multiple videos → Auto queued
• Auto rename captions
• Auto sort by Episode → Quality
• Supports 100+ videos at once

<b>📝 Placeholders:</b>
• {anime_name} - Anime name
• {ep} - Episode number  
• {season} - Season
• {quality} - Quality (480p/720p/1080p/4K)

<b>⚡ How to use:</b>
Just send videos (1 by 1 or multiple)
Bot will auto collect, sort & send back!
Or use /process to process manually"""
    
    await message.reply(help_text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("setcaption") & filters.private)
async def set_caption_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply(
            "<b>⚠️ Usage:</b>\n"
            "<code>/setcaption your template</code>\n\n"
            "<b>Placeholders:</b>\n"
            "• {anime_name}\n"
            "• {ep}\n"
            "• {season}\n"
            "• {quality}",
            parse_mode=ParseMode.HTML
        )
    
    if message.reply_to_message and message.reply_to_message.text:
        new_caption = message.reply_to_message.text
    else:
        new_caption = message.text.split(" ", 1)[1]
    
    user_captions[message.from_user.id] = new_caption
    
    preview = parse_caption_template(new_caption, {
        'anime_name': 'Demon Slayer',
        'ep': '05',
        'season': 'S01',
        'quality': '1080p'
    })
    
    await message.reply(
        f"<b>✅ Caption template set!</b>\n\n"
        f"<b>Preview:</b>\n{preview}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("viewcaption") & filters.private)
async def view_caption_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    current = user_captions.get(message.from_user.id, DEFAULT_CAPTION)
    preview = parse_caption_template(current, {
        'anime_name': 'Attack on Titan',
        'ep': '12',
        'season': 'S04',
        'quality': '720p'
    })
    
    await message.reply(
        f"<b>📝 Current Caption:</b>\n<code>{current}</code>\n\n"
        f"<b>Preview:</b>\n{preview}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("resetcaption") & filters.private)
async def reset_caption_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    user_captions.pop(message.from_user.id, None)
    
    await message.reply(
        "<b>✅ Caption reset to default!</b>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("process") & filters.private)
async def process_handler(client: Client, message: Message):
    """Manually trigger processing of queued videos"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    
    if not video_queues[user_id]:
        return await message.reply("<b>ℹ️ No videos in queue!</b>", parse_mode=ParseMode.HTML)
    
    if processing_status.get(user_id, False):
        return await message.reply("<b>⏳ Already processing! Wait...</b>", parse_mode=ParseMode.HTML)
    
    await process_video_queue(user_id, message.chat.id)

@app.on_message(filters.command("clear") & filters.private)
async def clear_handler(client: Client, message: Message):
    """Clear video queue"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    count = len(video_queues[user_id])
    video_queues[user_id] = []
    
    await message.reply(
        f"<b>🗑️ Cleared {count} videos from queue!</b>",
        parse_mode=ParseMode.HTML
    )

# ========== AUTO VIDEO HANDLER ==========

@app.on_message((filters.video | filters.document | filters.animation) & filters.private)
async def auto_video_handler(client: Client, message: Message):
    """Automatically queue videos and process them"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    
    # Add to queue
    video_queues[user_id].append({
        'message': message,
        'timestamp': time.time()
    })
    
    queue_size = len(video_queues[user_id])
    
    # Show queue status
    if queue_size == 1:
        status = await message.reply(
            f"<b>📥 Video queued (1)</b>\n"
            f"<i>Send more videos or wait 3 seconds for auto-process...</i>",
            parse_mode=ParseMode.HTML
        )
        
        # Wait 3 seconds for more videos
        await asyncio.sleep(3)
        
        # If queue still has videos and not processing, process them
        if video_queues[user_id] and not processing_status.get(user_id, False):
            await process_video_queue(user_id, message.chat.id)
    else:
        # Update status for additional videos
        if queue_size % 10 == 0 or queue_size in [5, 10, 25, 50]:
            await message.reply(
                f"<b>📥 Videos in queue: {queue_size}</b>\n"
                f"<i>Keep sending or bot will auto-process...</i>",
                parse_mode=ParseMode.HTML
            )

# ========== BATCH RENAME (RANGE) ==========

@app.on_message(filters.command("rename") & filters.private)
async def rename_handler(client: Client, message: Message):
    """Batch rename by message range"""
    if not is_admin(message.from_user.id):
        return
    
    await message.reply(
        "<b>🔄 Batch Rename Mode</b>\n\n"
        "1. Reply to FIRST message with <code>/startbatch</code>\n"
        "2. Reply to LAST message with <code>/endbatch</code>\n\n"
        "<i>Bot will process all videos between them!</i>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("startbatch") & filters.private)
async def startbatch_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to first message!")
    
    user_id = message.from_user.id
    user_rename_sessions[user_id] = {
        'start_id': message.reply_to_message.id,
        'chat_id': message.chat.id
    }
    
    await message.reply(
        f"<b>✅ Start marked (ID: {message.reply_to_message.id})</b>\n"
        f"Now reply to LAST message with <code>/endbatch</code>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("endbatch") & filters.private)
async def endbatch_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to last message!")
    
    user_id = message.from_user.id
    
    if user_id not in user_rename_sessions:
        return await message.reply("⚠️ First use /startbatch!")
    
    session = user_rename_sessions[user_id]
    start_id = session['start_id']
    end_id = message.reply_to_message.id
    chat_id = session['chat_id']
    
    if end_id <= start_id:
        return await message.reply("⚠️ End must be after start!")
    
    if (end_id - start_id) > 10000:
        return await message.reply("⚠️ Max 10000 messages allowed!")
    
    await message.reply(
        f"<b>⏳ Processing messages {start_id} to {end_id}...</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Collect messages
    videos = []
    caption_template = user_captions.get(user_id, DEFAULT_CAPTION)
    
    for msg_id in range(start_id, end_id + 1):
        try:
            msg = await client.get_messages(chat_id, msg_id)
            if msg and (msg.video or msg.document):
                info = extract_info_from_caption(msg.caption or "")
                if not info['anime_name']:
                    filename = msg.video.file_name if msg.video else msg.document.file_name
                    if filename:
                        info = extract_info_from_filename(filename)
                
                videos.append({
                    'msg': msg,
                    'info': info,
                    'ep_num': int(info['ep']) if str(info['ep']).isdigit() else 999,
                    'quality_priority': get_quality_priority(info['quality'])
                })
        except:
            continue
    
    if not videos:
        return await message.reply("<b>❌ No videos found!</b>")
    
    # Sort
    videos.sort(key=lambda x: (x['ep_num'], x['quality_priority']))
    
    # Send
    status = await message.reply(f"<b>⚡ Sending {len(videos)} videos...</b>")
    
    for idx, item in enumerate(videos, 1):
        try:
            new_caption = parse_caption_template(caption_template, item['info'])
            
            if item['msg'].video:
                await client.send_video(chat_id, item['msg'].video.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
            else:
                await client.send_document(chat_id, item['msg'].document.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
            
            if idx % 10 == 0:
                await status.edit_text(f"<b>⏳ Sent {idx}/{len(videos)}...</b>")
            
            await asyncio.sleep(0.5)
        except:
            continue
    
    await status.edit_text(f"<b>✅ Done! Sent {len(videos)} videos sorted!</b>")
    del user_rename_sessions[user_id]

# ========== MAIN ==========

if __name__ == "__main__":
    print("🤖 Caption Changer Bot Starting...")
    app.run()
