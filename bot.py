import os
import re
import asyncio
from pyrofork import Client, filters, idle
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
user_captions = {}  # user_id -> custom caption
user_rename_sessions = {}  # user_id -> {chat_id, start_msg_id, end_msg_id}

# Quality order for sorting (lowest to highest)
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
    workers=100  # High speed processing
)

# ========== HELPER FUNCTIONS ==========

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def extract_info_from_caption(caption: str) -> dict:
    """Extract anime info from original caption"""
    info = {
        'anime_name': '',
        'ep': 'N/A',
        'season': 'S01',
        'quality': '1080p'
    }
    
    if not caption:
        return info
    
    # Pattern 1: 📟 Episode - 24  ( S01 )
    ep_match = re.search(r'[Ee]pisode\s*[-:]?\s*(\d+)', caption)
    if ep_match:
        info['ep'] = ep_match.group(1)
    
    # Pattern 2: ⌬ Episode: 07
    if info['ep'] == 'N/A':
        ep_match2 = re.search(r'[Ee]pisode\s*[:=]\s*(\d+)', caption)
        if ep_match2:
            info['ep'] = ep_match2.group(1)
    
    # Season patterns
    season_match = re.search(r'[Ss]0?(\d+)', caption)
    if season_match:
        info['season'] = f"S0{season_match.group(1)}"
    
    # Quality patterns
    quality_patterns = [
        r'(\d{3,4}p)',  # 1080p, 720p, 480p
        r'4[Kk]',       # 4K
        r'2[Kk]',       # 2K
        r'8[Kk]',       # 8K
    ]
    for pattern in quality_patterns:
        q_match = re.search(pattern, caption, re.IGNORECASE)
        if q_match:
            info['quality'] = q_match.group(0).lower()
            break
    
    # Anime name extraction
    # Pattern: 🎬 ᴀɴɪᴍᴇ: To Be Hero X
    anime_match = re.search(r'[🎬📟]\s*[Aa]nime[:\-]?\s*([^\n]+)', caption)
    if anime_match:
        info['anime_name'] = anime_match.group(1).strip()
    else:
        # Try to get from first line or default
        lines = caption.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            # Remove emojis and clean
            clean = re.sub(r'[^\w\s\-]', '', first_line).strip()
            if clean and len(clean) > 2:
                info['anime_name'] = clean
    
    return info

def get_quality_priority(quality: str) -> int:
    """Get sorting priority for quality"""
    q = quality.lower().replace(' ', '')
    for key, value in QUALITY_ORDER.items():
        if key in q:
            return value
    return 99

def parse_caption_template(template: str, info: dict) -> str:
    """Parse caption template with placeholders"""
    try:
        return template.format(**info)
    except:
        return DEFAULT_CAPTION.format(**info)

def extract_info_from_filename(filename: str) -> dict:
    """Extract info from video filename"""
    info = {
        'anime_name': '',
        'ep': 'N/A',
        'season': 'S01',
        'quality': '1080p'
    }
    
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Episode pattern
    ep_match = re.search(r'[Ee]p?(\d+)|[Ee]pisode\s*(\d+)', name, re.IGNORECASE)
    if ep_match:
        ep_num = ep_match.group(1) or ep_match.group(2)
        info['ep'] = ep_num
    
    # Season pattern
    season_match = re.search(r'[Ss]0?(\d+)', name, re.IGNORECASE)
    if season_match:
        info['season'] = f"S0{season_match.group(1)}"
    
    # Quality pattern
    q_match = re.search(r'(\d{3,4}p|4[Kk]|2[Kk]|8[Kk])', name, re.IGNORECASE)
    if q_match:
        info['quality'] = q_match.group(0).lower()
    
    # Anime name (everything before episode/season)
    name_clean = re.sub(r'[._\-]', ' ', name)
    anime_match = re.split(r'[Ss]\d+|[Ee]p?\d+', name_clean, flags=re.IGNORECASE)[0]
    if anime_match:
        info['anime_name'] = anime_match.strip()
    
    return info

# ========== COMMAND HANDLERS ==========

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Start command handler"""
    if not is_admin(message.from_user.id):
        return await message.reply("⚠️ You are not authorized to use this bot.")
    
    await message.reply(
        "<blockquote>Jinda hu abhi..</blockquote>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    """Help command handler"""
    if not is_admin(message.from_user.id):
        return
    
    help_text = """<b>📋 Available Commands:</b>

<code>/start</code> - Check if bot is alive
<code>/help</code> - Show this help message
<code>/setcaption</code> - Set custom caption template
<code>/viewcaption</code> - View current caption template
<code>/resetcaption</code> - Reset to default caption
<code>/rename</code> - Start batch rename session

<b>📝 Caption Placeholders:</b>
• <code>{anime_name}</code> - Anime name
• <code>{ep}</code> - Episode number
• <code>{season}</code> - Season number
• <code>{quality}</code> - Video quality

<b>⚡ Rename Usage:</b>
1. Send <code>/rename</code>
2. Reply to the FIRST message of batch with <code>/startbatch</code>
3. Reply to the LAST message of batch with <code>/endbatch</code>
4. Bot will process all messages between them

<b>🔰 Admin Only Bot</b>"""
    
    await message.reply(help_text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("setcaption") & filters.private)
async def set_caption_handler(client: Client, message: Message):
    """Set custom caption template"""
    if not is_admin(message.from_user.id):
        return
    
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply(
            "<b>⚠️ Usage:</b>\n"
            "<code>/setcaption your caption template</code>\n\n"
            "<b>Or reply to a message with caption template</b>\n\n"
            "<b>Available placeholders:</b>\n"
            "• {anime_name}\n"
            "• {ep}\n"
            "• {season}\n"
            "• {quality}",
            parse_mode=ParseMode.HTML
        )
    
    # Get caption from command or reply
    if message.reply_to_message and message.reply_to_message.text:
        new_caption = message.reply_to_message.text
    else:
        new_caption = message.text.split(" ", 1)[1]
    
    user_captions[message.from_user.id] = new_caption
    
    # Preview
    preview_info = {
        'anime_name': 'Demon Slayer',
        'ep': '05',
        'season': 'S01',
        'quality': '1080p'
    }
    preview = parse_caption_template(new_caption, preview_info)
    
    await message.reply(
        f"<b>✅ Caption template set!</b>\n\n"
        f"<b>📊 Preview:</b>\n{preview}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("viewcaption") & filters.private)
async def view_caption_handler(client: Client, message: Message):
    """View current caption template"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    current = user_captions.get(user_id, DEFAULT_CAPTION)
    
    preview_info = {
        'anime_name': 'Attack on Titan',
        'ep': '12',
        'season': 'S04',
        'quality': '720p'
    }
    preview = parse_caption_template(current, preview_info)
    
    await message.reply(
        f"<b>📝 Current Caption Template:</b>\n<code>{current}</code>\n\n"
        f"<b>📊 Preview:</b>\n{preview}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("resetcaption") & filters.private)
async def reset_caption_handler(client: Client, message: Message):
    """Reset caption to default"""
    if not is_admin(message.from_user.id):
        return
    
    user_captions.pop(message.from_user.id, None)
    
    preview_info = {
        'anime_name': 'One Piece',
        'ep': '1080',
        'season': 'S01',
        'quality': '1080p'
    }
    preview = parse_caption_template(DEFAULT_CAPTION, preview_info)
    
    await message.reply(
        f"<b>✅ Caption reset to default!</b>\n\n"
        f"<b>📊 Preview:</b>\n{preview}",
        parse_mode=ParseMode.HTML
    )

# ========== RENAME SESSION HANDLERS ==========

@app.on_message(filters.command("rename") & filters.private)
async def rename_start_handler(client: Client, message: Message):
    """Start rename batch session"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    user_rename_sessions[user_id] = {'step': 'waiting_first'}
    
    await message.reply(
        "<b>🔄 Batch Rename Mode Activated!</b>\n\n"
        "1️⃣ <b>Reply to the FIRST message</b> of the batch with <code>/startbatch</code>\n"
        "2️⃣ <b>Reply to the LAST message</b> of the batch with <code>/endbatch</code>\n\n"
        "<i>Bot will process all video messages between them, rename captions, and sort by episode & quality.</i>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("startbatch") & filters.private)
async def start_batch_handler(client: Client, message: Message):
    """Mark first message of batch"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    
    if user_id not in user_rename_sessions:
        return await message.reply("⚠️ First send /rename to start a session!")
    
    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to the first message of the batch!")
    
    session = user_rename_sessions[user_id]
    session['chat_id'] = message.chat.id
    session['start_msg_id'] = message.reply_to_message.id
    session['step'] = 'waiting_last'
    
    await message.reply(
        f"<b>✅ First message marked (ID: {message.reply_to_message.id})</b>\n\n"
        f"Now reply to the <b>LAST message</b> with <code>/endbatch</code>",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("endbatch") & filters.private)
async def end_batch_handler(client: Client, message: Message):
    """Mark last message and process batch"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    
    if user_id not in user_rename_sessions:
        return await message.reply("⚠️ First send /rename to start a session!")
    
    session = user_rename_sessions[user_id]
    
    if session.get('step') != 'waiting_last':
        return await message.reply("⚠️ First mark the start with /startbatch!")
    
    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to the last message of the batch!")
    
    session['end_msg_id'] = message.reply_to_message.id
    
    # Validate range
    if session['end_msg_id'] < session['start_msg_id']:
        return await message.reply("⚠️ End message must be after start message!")
    
    # Process batch
    status_msg = await message.reply("<b>⏳ Processing batch...</b>", parse_mode=ParseMode.HTML)
    
    try:
        await process_batch(client, user_id, session, status_msg)
    except Exception as e:
        await status_msg.edit(f"<b>❌ Error:</b> {str(e)}")
    finally:
        user_rename_sessions.pop(user_id, None)

async def process_batch(client: Client, user_id: int, session: dict, status_msg: Message):
    """Process the batch of messages"""
    chat_id = session['chat_id']
    start_id = session['start_msg_id']
    end_id = session['end_msg_id']
    
    # Get user caption template
    caption_template = user_captions.get(user_id, DEFAULT_CAPTION)
    
    # Collect all video messages
    video_messages = []
    
    await status_msg.edit_text(
        f"<b>🔍 Scanning messages from {start_id} to {end_id}...</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Iterate through message range
    current_id = start_id
    batch_size = 0
    
    while current_id <= end_id:
        try:
            msg = await client.get_messages(chat_id, current_id)
            
            # Check if message has video
            if msg and (msg.video or msg.document or msg.animation):
                # Extract info from existing caption or filename
                info = None
                if msg.caption:
                    info = extract_info_from_caption(msg.caption)
                
                # If no info from caption, try filename
                if not info or info['anime_name'] == '':
                    filename = ""
                    if msg.video and msg.video.file_name:
                        filename = msg.video.file_name
                    elif msg.document and msg.document.file_name:
                        filename = msg.document.file_name
                    
                    if filename:
                        info = extract_info_from_filename(filename)
                
                if not info:
                    info = {'anime_name': 'Unknown', 'ep': 'N/A', 'season': 'S01', 'quality': '1080p'}
                
                video_messages.append({
                    'msg': msg,
                    'info': info,
                    'quality_priority': get_quality_priority(info['quality']),
                    'ep_num': int(info['ep']) if info['ep'].isdigit() else 999
                })
                batch_size += 1
                
        except Exception as e:
            pass  # Skip deleted/inaccessible messages
        
        current_id += 1
        
        # Update status every 50 messages
        if (current_id - start_id) % 50 == 0:
            await status_msg.edit_text(
                f"<b>🔍 Scanning... ({current_id - start_id} messages checked, {batch_size} videos found)</b>",
                parse_mode=ParseMode.HTML
            )
    
    if not video_messages:
        return await status_msg.edit("<b>❌ No video messages found in this range!</b>")
    
    # Sort by episode number, then by quality priority
    video_messages.sort(key=lambda x: (x['ep_num'], x['quality_priority']))
    
    await status_msg.edit_text(
        f"<b>✅ Found {len(video_messages)} videos</b>\n"
        f"<b>⚡ Starting rename and send...</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Process and send each video with new caption
    success_count = 0
    failed_count = 0
    
    for idx, item in enumerate(video_messages, 1):
        try:
            msg = item['msg']
            info = item['info']
            
            # Generate new caption
            new_caption = parse_caption_template(caption_template, info)
            
            # Copy message with new caption
            if msg.video:
                await client.send_video(
                    chat_id=chat_id,
                    video=msg.video.file_id,
                    caption=new_caption,
                    parse_mode=ParseMode.HTML,
                    duration=msg.video.duration,
                    width=msg.video.width,
                    height=msg.video.height,
                    thumb=msg.video.thumbs[0].file_id if msg.video.thumbs else None,
                    supports_streaming=True
                )
            elif msg.document:
                await client.send_document(
                    chat_id=chat_id,
                    document=msg.document.file_id,
                    caption=new_caption,
                    parse_mode=ParseMode.HTML,
                    thumb=msg.document.thumbs[0].file_id if msg.document.thumbs else None
                )
            elif msg.animation:
                await client.send_animation(
                    chat_id=chat_id,
                    animation=msg.animation.file_id,
                    caption=new_caption,
                    parse_mode=ParseMode.HTML
                )
            
            success_count += 1
            
            # Update progress every 5 videos
            if idx % 5 == 0 or idx == len(video_messages):
                await status_msg.edit_text(
                    f"<b>⏳ Progress: {idx}/{len(video_messages)}</b>\n"
                    f"✅ Success: {success_count}\n"
                    f"❌ Failed: {failed_count}",
                    parse_mode=ParseMode.HTML
                )
            
            # Small delay to avoid flood
            await asyncio.sleep(0.5)
            
        except Exception as e:
            failed_count += 1
            continue
    
    # Final status
    await status_msg.edit_text(
        f"<b>🎉 Batch Processing Complete!</b>\n\n"
        f"📊 <b>Total:</b> {len(video_messages)}\n"
        f"✅ <b>Success:</b> {success_count}\n"
        f"❌ <b>Failed:</b> {failed_count}\n\n"
        f"<i>Videos sorted by Episode → Quality (480p→720p→1080p→4K)</i>",
        parse_mode=ParseMode.HTML
    )

# ========== SINGLE VIDEO HANDLER ==========

@app.on_message((filters.video | filters.document | filters.animation) & filters.private)
async def single_video_handler(client: Client, message: Message):
    """Handle single video - rename caption and send back"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    caption_template = user_captions.get(user_id, DEFAULT_CAPTION)
    
    # Extract info
    info = None
    if message.caption:
        info = extract_info_from_caption(message.caption)
    
    # Try filename if no caption info
    if not info or info['anime_name'] == '':
        filename = ""
        if message.video and message.video.file_name:
            filename = message.video.file_name
        elif message.document and message.document.file_name:
            filename = message.document.file_name
        
        if filename:
            info = extract_info_from_filename(filename)
    
    if not info:
        info = {'anime_name': 'Unknown', 'ep': 'N/A', 'season': 'S01', 'quality': '1080p'}
    
    # Generate new caption
    new_caption = parse_caption_template(caption_template, info)
    
    # Send back with new caption
    try:
        if message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=message.video.file_id,
                caption=new_caption,
                parse_mode=ParseMode.HTML,
                duration=message.video.duration,
                width=message.video.width,
                height=message.video.height,
                thumb=message.video.thumbs[0].file_id if message.video.thumbs else None,
                supports_streaming=True,
                reply_to_message_id=message.id
            )
        elif message.document:
            await client.send_document(
                chat_id=message.chat.id,
                document=message.document.file_id,
                caption=new_caption,
                parse_mode=ParseMode.HTML,
                thumb=message.document.thumbs[0].file_id if message.document.thumbs else None,
                reply_to_message_id=message.id
            )
        elif message.animation:
            await client.send_animation(
                chat_id=message.chat.id,
                animation=message.animation.file_id,
                caption=new_caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id
            )
    except Exception as e:
        await message.reply(f"<b>❌ Error:</b> {str(e)}", parse_mode=ParseMode.HTML)

# ========== MAIN ==========

if __name__ == "__main__":
    print("🤖 Caption Changer Bot Starting...")
    app.run()
