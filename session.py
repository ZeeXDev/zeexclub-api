from pyrogram import Client

API_ID = 37641587
API_HASH = "9bce1167e828939f39452795e56202a9"
BOT_TOKEN = "8588309317:AAFjJNfUAba8Ate8gd2h3LcJN8F3f0mLXbQ"

app = Client(
    "zeexclub_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

with app:
    session_string = app.export_session_string()
    print("=" * 50)
    print("SESSION_STRING :")
    print(session_string)
    print("=" * 50)
