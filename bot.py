import os
import re
import asyncio
import logging
from pyrofork import Client, filters
from pyrofork.types import Message
from pyrofork.enums import ParseMode
from pyrofork.errors import FloodWait

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Better ADMIN_IDS parsing - handles single ID, multiple IDs, with/without commas
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = []
if admin_ids_str:
    # Remove any quotes that might be in the env variable
    admin_ids_str = admin_ids_str.replace('"', '').replace("'", "")
    # Split by comma or space and convert to int
    for id_str in admin_ids_str.replace(",", " ").split():
        try:
            ADMIN_IDS.append(int(id_str.strip()))
        except ValueError:
            logger.warning(f"Could not parse admin ID: {id_str}")

logger.info(f"=" * 50)
logger.info(f"ADMIN_IDS loaded: {ADMIN_IDS}")
logger.info(f"Raw ADMIN_IDS env: {os.environ.get('ADMIN_IDS', 'NOT SET')}")
logger.info(f"=" * 50)

# Default caption template with placeholders
DEFAULT_CAPTION = """<b><blockquote expandable>💫 {anime_name} 💫</blockquote>

‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote expandable>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# Global storage for user captions
user_captions = {}
rename_sessions = {}

# Quality priority for sorting (lower = better priority)
QUALITY_ORDER = {
    '480p': 1, '480': 1,
    '720p': 2, '720': 2, 'hd': 2,
    '1080p': 3, '1080': 3, 'fhd': 3, 'fullhd': 3,
    '2k': 4, '1440p': 4,
    '4k': 5, '2160p': 5, 'uhd': 5
}

# Initialize bot
app = Client(
    "caption_changer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=100,
    parse_mode=ParseMode.HTML
)

# ============ HELPER FUNCTIONS ============

def extract_info(text):
    """Extract anime name, episode, season, quality from caption"""
    info = {
        'anime_name': 'Unknown Anime',
        'ep': 'N/A',
        'season': '01',
        'quality': '1080p'
    }
    
    if not text:
        return info
    
    # Extract Episode
    ep_patterns = [
        r'[Ee]pisode\s*[-:]?\s*(\d+)',
        r'[Ee][Pp]\s*[-:]?\s*(\d+)',
        r'[#＃]\s*(\d+)',
        r'(?:^|\s)(\d{1,3})(?:\s|$)',
        r'(?:^|\s)(\d{1,3})\s*(?:\(|\.|\[)'
    ]
    for pattern in ep_patterns:
        match = re.search(pattern, text)
        if match:
            info['ep'] = match.group(1).zfill(2)
            break
    
    # Extract Season
    season_patterns = [
        r'[Ss]eason\s*[-:]?\s*(\d+)',
        r'[Ss](\d{1,2})',
        r'[Ss]0?(\d+)'
    ]
    for pattern in season_patterns:
        match = re.search(pattern, text)
        if match:
            info['season'] = match.group(1).zfill(2)
            break
    
    # Extract Quality
    quality_patterns = [
        r'(\d{3,4}p)',
        r'(480|720|1080|2160)',
        r'(4k|2k|uhd|fhd|hd)'
    ]
    for pattern in quality_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['quality'] = match.group(1).lower()
            if info['quality'] in ['4k', '2160', 'uhd']:
                info['quality'] = '2160p'
            elif info['quality'] in ['2k', '1440']:
                info['quality'] = '1440p'
            elif info['quality'] in ['1080', 'fhd']:
                info['quality'] = '1080p'
            elif info['quality'] in ['720', 'hd']:
                info['quality'] = '720p'
            elif info['quality'] in ['480']:
                info['quality'] = '480p'
            break
    
    # Extract Anime Name
    anime_patterns = [
        r'[Aa]nime\s*[-:]?\s*([^\n]+)',
        r'🎬\s*([^\n]+)',
        r'📟\s*([^\n]+)',
        r'💫\s*([^\n]+)',
        r'🎥\s*([^\n]+)'
    ]
    for pattern in anime_patterns:
        match = re.search(pattern, text)
        if match:
            info['anime_name'] = match.group(1).strip()[:50]
            break
    
    # If no anime name found, try first meaningful line
    if info['anime_name'] == 'Unknown Anime':
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 3 and not any(x in line.lower() for x in ['episode', 'season', 'quality', 'audio', 'language']):
                info['anime_name'] = line[:50]
                break
    
    return info

def get_quality_priority(quality_str):
    """Get sorting priority for quality"""
    q = quality_str.lower().replace('p', '')
    return QUALITY_ORDER.get(q, 99)

def parse_caption(template, info):
    """Replace placeholders in template with actual values"""
    caption = template
    caption = caption.replace('{anime_name}', info.get('anime_name', 'Unknown'))
    caption = caption.replace('{ep}', str(info.get('ep', 'N/A')))
    caption = caption.replace('{season}', str(info.get('season', '01')))
    caption = caption.replace('{quality}', info.get('quality', '1080p'))
    return caption

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# ============ COMMAND HANDLERS ============

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    """Start command handler"""
    user_id = message.from_user.id
    
    # Debug info
    logger.info(f"Start command from user: {user_id}")
    logger.info(f"ADMIN_IDS list: {ADMIN_IDS}")
    logger.info(f"Is admin check: {user_id in ADMIN_IDS}")
    
    if not is_admin(user_id):
        return await message.reply(
            f"⛔ You are not authorized to use this bot.\n\n"
            f"Your ID: <code>{user_id}</code>\n"
            f"Admin IDs: <code>{ADMIN_IDS}</code>",
            quote=True
        )
    
    await message.reply(
        "<blockquote>Jinda hu abhi..</blockquote>",
        quote=True
    )

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client, message: Message):
    """Help command handler"""
    if not is_admin(message.from_user.id):
        return await message.reply(f"Your ID: <code>{message.from_user.id}</code>", quote=True)
    
    help_text = """<b>🤖 Caption Changer Bot Commands</b>

<b>Basic Commands:</b>
/start - Check if bot is alive
/help - Show this help message

<b>Caption Commands:</b>
/setcaption - Set custom caption template
/mycaption - View your current caption
/resetcaption - Reset to default caption

<b>Rename Commands:</b>
/rename - Reply to a video to rename caption
/batchrename - Rename all messages between two points

<b>Placeholders:</b>
<code>{anime_name}</code> - Anime name
<code>{ep}</code> - Episode number
<code>{season}</code> - Season number
<code>{quality}</code> - Video quality

<b>Admin Only:</b>
Only admins can use this bot."""
    
    await message.reply(help_text, quote=True)

@app.on_message(filters.command("setcaption") & filters.private)
async def setcaption_handler(client, message: Message):
    """Set custom caption template"""
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ Not authorized.", quote=True)
    
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply(
            "<b>⚠️ Usage:</b>\n"
            "<code>/setcaption your caption template</code>\n\n"
            "<b>Available placeholders:</b>\n"
            "<code>{anime_name}</code> - Anime name\n"
            "<code>{ep}</code> - Episode number\n"
            "<code>{season}</code> - Season number\n"
            "<code>{quality}</code> - Quality",
            quote=True
        )
    
    if message.reply_to_message and message.reply_to_message.text:
        new_caption = message.reply_to_message.text
    else:
        new_caption = message.text.split(None, 1)[1]
    
    user_captions[message.from_user.id] = new_caption
    
    preview_info = {
        'anime_name': 'Demon Slayer',
        'ep': '05',
        'season': '01',
        'quality': '1080p'
    }
    preview = parse_caption(new_caption, preview_info)
    
    await message.reply(
        f"<b>✅ Caption template set!</b>\n\n"
        f"<b>Preview:</b>\n{preview}",
        quote=True
    )

@app.on_message(filters.command("mycaption") & filters.private)
async def mycaption_handler(client, message: Message):
    """Show current caption template"""
    if not is_admin(message.from_user.id):
        return
    
    caption = user_captions.get(message.from_user.id, DEFAULT_CAPTION)
    await message.reply(
        f"<b>📝 Your Caption Template:</b>\n\n"
        f"<code>{caption}</code>",
        quote=True
    )

@app.on_message(filters.command("resetcaption") & filters.private)
async def resetcaption_handler(client, message: Message):
    """Reset caption to default"""
    if not is_admin(message.from_user.id):
        return
    
    user_captions.pop(message.from_user.id, None)
    await message.reply("<b>✅ Caption reset to default!</b>", quote=True)

@app.on_message(filters.command("rename") & filters.private)
async def rename_handler(client, message: Message):
    """Rename caption of a single video"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        return await message.reply("⚠️ Reply to a video with /rename", quote=True)
    
    target_msg = message.reply_to_message
    
    if not target_msg.video and not target_msg.document:
        return await message.reply("⚠️ Reply to a video file.", quote=True)
    
    processing_msg = await message.reply("🔄 Processing...", quote=True)
    
    try:
        template = user_captions.get(message.from_user.id, DEFAULT_CAPTION)
        original_caption = target_msg.caption or ""
        info = extract_info(original_caption)
        new_caption = parse_caption(template, info)
        
        await target_msg.copy(
            chat_id=message.chat.id,
            caption=new_caption,
            parse_mode=ParseMode.HTML
        )
        
        await processing_msg.edit("✅ Caption renamed successfully!")
        
    except Exception as e:
        logger.error(f"Error in rename: {e}")
        await processing_msg.edit(f"❌ Error: {str(e)}")

@app.on_message(filters.command("batchrename") & filters.private)
async def batchrename_handler(client, message: Message):
    """Start batch rename session"""
    if not is_admin(message.from_user.id):
        return
    
    await message.reply(
        "<b>📦 Batch Rename Mode</b>\n\n"
        "Send the <b>first message link</b> to start.\n"
        "Format: <code>https://t.me/c/xxxx/123</code>",
        quote=True
    )
    rename_sessions[message.from_user.id] = {"step": "waiting_first"}

@app.on_message(filters.text & filters.private)
async def batch_input_handler(client, message: Message):
    """Handle batch rename inputs"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    if user_id not in rename_sessions:
        return
    
    session = rename_sessions[user_id]
    
    if session["step"] == "waiting_first":
        try:
            if "t.me" in message.text:
                parts = message.text.strip().split('/')
                msg_id = int(parts[-1])
                chat_id = parts[-2]
                if chat_id.startswith('c/'):
                    chat_id = int(f"-100{chat_id[2:]}")
                else:
                    chat_id = int(chat_id) if chat_id.lstrip('-').isdigit() else chat_id
            else:
                msg_id = int(message.text.strip())
                chat_id = message.chat.id
            
            session["first_msg"] = msg_id
            session["chat_id"] = chat_id
            session["step"] = "waiting_last"
            
            await message.reply(
                "<b>✅ First message recorded.</b>\n\n"
                "Now send the <b>last message link</b> or ID.",
                quote=True
            )
        except Exception as e:
            await message.reply(f"❌ Invalid format: {e}", quote=True)
    
    elif session["step"] == "waiting_last":
        try:
            if "t.me" in message.text:
                parts = message.text.strip().split('/')
                msg_id = int(parts[-1])
            else:
                msg_id = int(message.text.strip())
            
            session["last_msg"] = msg_id
            session["step"] = "confirm"
            
            await message.reply(
                f"<b>📊 Batch Summary:</b>\n"
                f"• From: <code>{session['first_msg']}</code>\n"
                f"• To: <code>{session['last_msg']}</code>\n\n"
                f"Send <code>/confirm</code> to start or <code>/cancel</code> to abort.",
                quote=True
            )
        except:
            await message.reply("❌ Invalid format.", quote=True)
    
    elif session["step"] == "confirm" and message.text == "/confirm":
        await process_batch_rename(client, message, session)
        del rename_sessions[user_id]
    
    elif message.text == "/cancel":
        del rename_sessions[user_id]
        await message.reply("❌ Batch rename cancelled.", quote=True)

async def process_batch_rename(client, message: Message, session):
    """Process batch rename with sorting"""
    first_msg = session["first_msg"]
    last_msg = session["last_msg"]
    chat_id = session["chat_id"]
    
    status_msg = await message.reply("🔄 Fetching messages...", quote=True)
    
    try:
        videos = []
        current = first_msg
        
        while current <= last_msg:
            try:
                msg = await client.get_messages(chat_id, current)
                if msg and (msg.video or msg.document):
                    caption = msg.caption or ""
                    info = extract_info(caption)
                    quality_priority = get_quality_priority(info.get('quality', '1080p'))
                    
                    videos.append({
                        'msg': msg,
                        'info': info,
                        'quality_priority': quality_priority,
                        'ep_num': int(info.get('ep', '0')) if info.get('ep', '0').isdigit() else 0
                    })
                
                current += 1
                
                if (current - first_msg) % 10 == 0:
                    await status_msg.edit(f"🔄 Fetched {len(videos)} videos...")
                    
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                logger.error(f"Error fetching msg {current}: {e}")
                current += 1
        
        if not videos:
            return await status_msg.edit("❌ No videos found.")
        
        videos.sort(key=lambda x: (x['ep_num'], x['quality_priority']))
        
        await status_msg.edit(f"✅ Found {len(videos)} videos. Sending...")
        
        template = user_captions.get(message.from_user.id, DEFAULT_CAPTION)
        
        success_count = 0
        for idx, video_data in enumerate(videos, 1):
            try:
                info = video_data['info']
                new_caption = parse_caption(template, info)
                
                await video_data['msg'].copy(
                    chat_id=message.chat.id,
                    caption=new_caption,
                    parse_mode=ParseMode.HTML
                )
                
                success_count += 1
                
                if idx % 5 == 0:
                    await status_msg.edit(f"📤 Progress: {idx}/{len(videos)} sent...")
                
                await asyncio.sleep(0.5)
                
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await video_data['msg'].copy(
                    chat_id=message.chat.id,
                    caption=new_caption,
                    parse_mode=ParseMode.HTML
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Error: {e}")
                continue
        
        await status_msg.edit(
            f"<b>✅ Complete!</b>\n\n"
            f"📊 Total: {len(videos)}\n"
            f"✅ Sent: {success_count}\n"
            f"❌ Failed: {len(videos) - success_count}"
        )
        
    except Exception as e:
        logger.error(f"Batch error: {e}")
        await status_msg.edit(f"❌ Error: {str(e)}")

# ============ MAIN ============

if __name__ == "__main__":
    print("Starting Caption Changer Bot...")
    print(f"Admin IDs: {ADMIN_IDS}")
    app.run()
