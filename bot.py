import re
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv

load_dotenv()

API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = list(map(int, os.environ.get("ADMIN_IDS", "0").split(",")))

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DEFAULT_CAPTION = (
    "<b><blockquote>ð« {anime_name} ð«</blockquote>\n"
    "‣ Episode : {ep}\n"
    "‣ Season  : {season}\n"
    "‣ Quality : {quality}\n"
    "‣ Audio   : Hindi Dub ð️ | Official\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<blockquote>ð For More Join\n"
    "ð° [@KENSHIN_ANIME]</blockquote>\n"
    "━━━━━━━━━━━━━━━━━━━━━</b>"
)

QUALITY_RANK = {
    "480p": 1, "720p": 2, "1080p": 3,
    "2k": 4, "4k": 5, "2160p": 5
}

user_captions: dict[int, str] = {}
batch_queue:   dict[int, list] = {}


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def parse_caption(text: str) -> dict:
    text = text or ""
    data = {"anime_name": "Unknown", "ep": "01", "season": "01", "quality": "1080p"}

    m = re.search(r'(?:episode|ep|eᴘɪˢᴏᴅᴇ|U0001F4DF)[^d]*(d+)', text, re.IGNORECASE)
    if m:
        data["ep"] = m.group(1).zfill(2)

    m = re.search(r'(?:season|s)[^d]*(d+)', text, re.IGNORECASE)
    if m:
        data["season"] = m.group(1).zfill(2)
    elif re.search(r'S¹', text):
        data["season"] = "01"

    m = re.search(r'(2160p|4k|1080p|720p|480p)', text, re.IGNORECASE)
    if m:
        data["quality"] = m.group(1).lower().replace("4k", "4K").replace("2160p", "4K")

    for line in text.split("
"):
        clean = re.sub(
            r'[━-=_•*|#@✻✾✵⧉⯌►➳U0001F3ACU0001F4DFU0001F3A7U0001F4C0⧉]|'
            r'[.*?]|episode.*|eps*d.*|season.*|quality.*|audio.*|'
            r'language.*|powered.*|ᴀɴɪᴏᴋᴇs*:',
            '', line, flags=re.IGNORECASE
        ).strip()
        clean = re.sub(r's+', ' ', clean).strip()
        if len(clean) > 2 and not clean.startswith("@"):
            data["anime_name"] = clean
            break

    return data


def build_caption(uid: int, data: dict) -> str:
    template = user_captions.get(uid, DEFAULT_CAPTION)
    return template.format(**data)


@app.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    await msg.reply("<blockquote>Jinda hu abhi..</blockquote>", parse_mode="html")


@app.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    await msg.reply(
        "<b>ð Help Menu</b>\n\n"
        "/start — Bot status check\n"
        "/setcaption — Custom caption set karo (placeholders: {anime_name}, {ep}, {season}, {quality})\n"
        "/resetcaption — Default caption restore karo\n"
        "/batch — Queued videos ko sorted bhejo\n"
        "/clearbatch — Queue clear karo\n"
        "/help — Yeh menu\n\n"
        "<b>Usage:</b>\n"
        "1. Koi bhi video forward karo — bot caption replace karke bhejega.\n"
        "2. Multiple videos bhejo → /batch se sorted (ep + quality) bhejega.",
        parse_mode="html"
    )


@app.on_message(filters.command("setcaption"))
async def cmd_setcaption(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Sirf admins ke liye hai.")
    parts = msg.text.split(None, 1)
    if len(parts) < 2:
        return await msg.reply(
            "Usage:\n<code>/setcaption &lt;your template&gt;</code>\n\n"
            "Placeholders: <code>{anime_name}</code> <code>{ep}</code> "
            "<code>{season}</code> <code>{quality}</code>",
            parse_mode="html"
        )
    user_captions[msg.from_user.id] = parts[1].strip()
    await msg.reply("✅ Caption template save ho gaya.")


@app.on_message(filters.command("resetcaption"))
async def cmd_resetcaption(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Sirf admins ke liye hai.")
    user_captions.pop(msg.from_user.id, None)
    await msg.reply("✅ Default caption restore ho gaya.")


@app.on_message(filters.command("clearbatch"))
async def cmd_clearbatch(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Sirf admins ke liye hai.")
    batch_queue.pop(msg.from_user.id, None)
    await msg.reply("ð¡️ Batch queue clear ho gayi.")


@app.on_message(filters.command("batch"))
async def cmd_batch(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Sirf admins ke liye hai.")
    uid   = msg.from_user.id
    queue = batch_queue.get(uid, [])
    if not queue:
        return await msg.reply("Queue khali hai. Pehle videos bhejo.")

    queue.sort(key=lambda x: (x[0], x[1]))

    await msg.reply(f"ð¤ {len(queue)} videos sorted order mein bhej raha hoon...")
    for _, _, original_msg, data in queue:
        caption = build_caption(uid, data)
        await original_msg.copy(msg.chat.id, caption=caption, parse_mode="html")

    batch_queue[uid] = []
    await msg.reply("✅ Sab videos bhej diye. Queue clear.")


@app.on_message(filters.video | filters.document)
async def handle_video(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return

    uid     = msg.from_user.id
    caption = msg.caption or ""
    data    = parse_caption(caption)
    ep_num  = int(data["ep"]) if data["ep"].isdigit() else 0
    q_rank  = QUALITY_RANK.get(data["quality"].lower(), 3)

    if uid not in batch_queue:
        batch_queue[uid] = []
    batch_queue[uid].append((ep_num, q_rank, msg, data))

    new_caption = build_caption(uid, data)
    await msg.copy(msg.chat.id, caption=new_caption, parse_mode="html")
    await msg.reply(
        f"✅ Caption replace ho gaya.\n"
        f"ð¦ Batch queue mein bhi add ho gaya (total: {len(batch_queue[uid])}).\n"
        f"Sorted bhejne ke liye /batch use karo.",
        quote=True
    )


if __name__ == "__main__":
    print("Bot chal raha hai...")
    app.run()
