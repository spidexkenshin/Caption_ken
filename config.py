import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

DEFAULT_CAPTION = """<b><blockquote> ✨ {anime} ✨</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : {audio} | Official🎙️
━━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join: [@KENSHIN_ANIME & MANWHA_VERSE]</blockquote>
━━━━━━━━━━━━━━━━━━━━━━</b>"""
