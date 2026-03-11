import os
import re
import asyncio
from pyrogram import Client, filters, enums

# --- CONFIGURATION (Set these in Railway Variables) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Enter Admin IDs separated by spaces (e.g. "123456789 987654321")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]

# --- DEFAULT CAPTION ---
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# --- IN-MEMORY DB ---
user_captions = {}
batch_states = {}

app = Client(
    "CaptionRenamerBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- HELPER FUNCTIONS ---
def parse_caption(text, filename=""):
    """Extracts Anime, Episode, Season, and Quality from text using Regex"""
    ep_match = re.search(r'(?i)(?:ep|episode)[\s\:\-]*(\d+)', text)
    season_match = re.search(r'(?i)(?:s|season)[\s\:\-]*(\d+)', text)
    quality_match = re.search(r'(?i)(\d{3,4}p|4k)', text)
    anime_match = re.search(r'(?i)(?:anime|ᴀɴɪᴍᴇ)[\s\:\-]*([^\n\r━]+)', text)
    
    ep = ep_match.group(1) if ep_match else "01"
    season = season_match.group(1).zfill(2) if season_match else "01"
    quality = quality_match.group(1).lower() if quality_match else "Unknown"
    
    anime_name = "Unknown Anime"
    if anime_match:
        anime_name = anime_match.group(1).strip()
    elif filename:
        anime_name = filename.split('.')[0]
        
    return {
        "anime_name": anime_name,
        "ep": ep.zfill(2),
        "season": season,
        "quality": quality
    }

def get_sort_keys(item):
    """Sorting logic: First by episode, then by quality"""
    ep = int(item['parsed']['ep']) if str(item['parsed']['ep']).isdigit() else 0
    q_str = str(item['parsed']['quality']).lower()
    
    if '480' in q_str: q_val = 1
    elif '720' in q_str: q_val = 2
    elif '1080' in q_str: q_val = 3
    elif '2160' in q_str or '4k' in q_str: q_val = 4
    else: q_val = 0
    
    return (ep, q_val)

def parse_link(link):
    """Extracts Chat ID and Message ID from Telegram link"""
    parts = link.strip().rstrip('/').split('/')
    msg_id = int(parts[-1])
    if 'c' in parts:
        chat_id = int("-100" + parts[-2])
    else:
        chat_id = parts[-2]
    return chat_id, msg_id

# --- COMMANDS ---

@app.on_message(filters.command("start") & filters.user(ADMINS))
async def start_cmd(client, message):
    await message.reply("<blockquote> Jinda hu abhi.. </blockquote>", parse_mode=enums.ParseMode.HTML)

@app.on_message(filters.command("help") & filters.user(ADMINS))
async def help_cmd(client, message):
    text = """
<b>🛠 Admin Help Menu</b>

• `/start` - Check if bot is alive.
• `/setcaption <your_html_caption>` - Set a custom format.
• `/setcaption default` - Revert to default caption.
• `/rename` - Start bulk renaming (sorted fast copy).

<i>Placeholders available for caption:</i> `{anime_name}`, `{ep}`, `{season}`, `{quality}`
"""
    await message.reply(text)

@app.on_message(filters.command("setcaption") & filters.user(ADMINS))
async def setcaption_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Send caption text format after the command.\nExample: `/setcaption {anime_name} - {ep}`")
    
    custom_cap = message.text.split(" ", 1)[1]
    if custom_cap.strip().lower() == "default":
        if message.from_user.id in user_captions:
            del user_captions[message.from_user.id]
        await message.reply("✅ Caption reset to Default.")
    else:
        user_captions[message.from_user.id] = custom_cap
        await message.reply("✅ Custom caption saved successfully!")

@app.on_message(filters.command("rename") & filters.user(ADMINS))
async def rename_batch_cmd(client, message):
    batch_states[message.from_user.id] = {"step": 1}
    await message.reply("🔗 Send the **First Message Link** of the channel/chat:")

@app.on_message(filters.text & filters.user(ADMINS) & ~filters.command(["start", "help", "setcaption", "rename"]))
async def process_links(client, message):
    user_id = message.from_user.id
    if user_id not in batch_states:
        return
        
    state = batch_states[user_id]
    text = message.text
    
    if state["step"] == 1:
        try:
            chat_id, msg_id = parse_link(text)
            batch_states[user_id]["chat_id"] = chat_id
            batch_states[user_id]["start_id"] = msg_id
            batch_states[user_id]["step"] = 2
            await message.reply("✅ Got it! Now send the **Last Message Link**:")
        except Exception:
            await message.reply("❌ Invalid Link format! Try again or use /rename to restart.")
            
    elif state["step"] == 2:
        try:
            _, end_id = parse_link(text)
            chat_id = batch_states[user_id]["chat_id"]
            start_id = batch_states[user_id]["start_id"]
            
            if start_id > end_id:
                start_id, end_id = end_id, start_id # Swap if inverted
                
            del batch_states[user_id] # Clear state
            
            status_msg = await message.reply(f"⏳ Processing messages from **{start_id}** to **{end_id}**...\n\n_Fetching, Extracting, and Sorting. Please wait..._")
            asyncio.create_task(process_batch(client, message, chat_id, start_id, end_id, status_msg))
            
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

# --- CORE BATCH PROCESSING ---
async def process_batch(client, message, chat_id, start_id, end_id, status_msg):
    user_id = message.from_user.id
    caption_template = user_captions.get(user_id, DEFAULT_CAPTION)
    
    msg_ids_to_fetch = list(range(start_id, end_id + 1))
    valid_items = []
    
    # 1. Fetch all messages in chunks to avoid API limits
    chunk_size = 200
    for i in range(0, len(msg_ids_to_fetch), chunk_size):
        chunk = msg_ids_to_fetch[i:i+chunk_size]
        try:
            messages = await client.get_messages(chat_id, chunk)
            for msg in messages:
                if msg.empty or not (msg.video or msg.document):
                    continue
                    
                text = msg.caption or ""
                filename = ""
                if msg.video: filename = msg.video.file_name or ""
                elif msg.document: filename = msg.document.file_name or ""
                
                parsed_data = parse_caption(text, filename)
                valid_items.append({
                    "msg_id": msg.id,
                    "parsed": parsed_data
                })
        except Exception as e:
            print(f"Fetch Error: {e}")
            
        await asyncio.sleep(1) # Prevent FloodWaits while fetching
        
    if not valid_items:
        return await status_msg.edit("❌ No videos or documents found in this range!")

    # 2. Sort Items (Episode wise, then Quality wise)
    valid_items.sort(key=get_sort_keys)
    
    await status_msg.edit(f"🔄 Sorting Complete. Found **{len(valid_items)}** videos. Now Copying at full speed...")

    # 3. Send them fast using copy_message with new caption
    sent_count = 0
    for item in valid_items:
        parsed = item["parsed"]
        try:
            new_caption = caption_template.format(
                anime_name=parsed["anime_name"],
                ep=parsed["ep"],
                season=parsed["season"],
                quality=parsed["quality"]
            )
        except KeyError:
            new_caption = caption_template # Fallback if user set bad placeholders
            
        try:
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=item["msg_id"],
                caption=new_caption,
                parse_mode=enums.ParseMode.HTML
            )
            sent_count += 1
            await asyncio.sleep(1.2) # Sleep to respect Telegram limits (~30 msgs/sec, but safe limit is 1-2 sec)
        except Exception as e:
            print(f"Send Error for Msg {item['msg_id']}: {e}")
            
    await status_msg.edit(f"✅ **Batch Completed!**\n\nSuccessfully Sorted and Renamed **{sent_count}** videos.")

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
