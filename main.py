import os
import json
import asyncio
import aiohttp
import random
import zipfile
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyromod.exceptions.listener_timeout import ListenerTimeout
from flask import Flask

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config ---
API_ID = int(os.environ.get("API_ID", "24473318"))
API_HASH = os.environ.get("API_HASH", "e7dd0576c5ac0ff8f90971d6bb04c8f5")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
auth_users = [6132794263]  # List of authorized Telegram user IDs

# --- Flask (Keep-alive for Render/Koyeb) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# --- Bot Init ---
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UI Assets ---
image_list = [
    "https://graph.org/file/8b1f4146a8d6b43e5b2bc-be490579da043504d5.jpg",
    "https://graph.org/file/b75dab2b3f7eaff612391-282aa53538fd3198d4.jpg",
    "https://graph.org/file/38de0b45dd9144e524a33-0205892dd05593774b.jpg",
]

# ---------------- Helpers ----------------
async def fetch_json(session, url, headers=None, params=None, data=None, method="GET"):
    try:
        async with session.request(method, url, headers=headers, params=params, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()
    except Exception as e:
        logging.error(f"Fetch error for {url}: {e}")
        return None

# ---------------- Bot Handlers ----------------
@bot.on_message(filters.command(["start"]))
async def start_handler(client: Client, message: Message):
    random_image_url = random.choice(image_list)
    keyboard = [
        [InlineKeyboardButton("🚀 Physics Wallah without Purchase 🚀", callback_data="pwwp")],
        [InlineKeyboardButton("📘 Classplus without Purchase 📘", callback_data="cpwp")],
        [InlineKeyboardButton("📒 Appx Without Purchase 📒", callback_data="appxwp")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_photo(
        photo=random_image_url,
        caption="**PLEASE👇PRESS👇HERE**",
        quote=True,
        reply_markup=reply_markup,
    )

@bot.on_callback_query(filters.regex(r"^pwwp$"))
async def pwwp_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer()
    if user_id not in auth_users:
        await client.send_message(callback_query.message.chat.id, "**You are not authorized.**")
        return
    await process_pwwp(client, callback_query.message, user_id)

# ---------------- PWWP Flow ----------------
async def process_pwwp(client: Client, m: Message, user_id: int):
    editable = await m.reply_text("**Enter Working Access Token OR Phone Number**")

    try:
        input1 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
        raw_text1 = (input1.text or "").strip()
        await input1.delete(True)
    except ListenerTimeout:
        await editable.edit("**Timeout! You took too long to respond.**")
        return
    except Exception:
        await editable.edit("**Input error. Try again.**")
        return

    headers = {
        "Host": "api.penpencil.co",
        "client-id": "5eb393ee95fab7468a79d189",
        "client-version": "1910",
        "user-agent": "Mozilla/5.0",
        "randomid": "72012511-256c-4e1c-b4c7-29d67136af37",
        "client-type": "WEB",
        "content-type": "application/json; charset=utf-8",
    }

    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            if raw_text1.isdigit() and len(raw_text1) == 10:
                # Phone login flow
                phone = raw_text1
                data = {"username": phone, "countryCode": "+91", "organizationId": "5eb393ee95fab7468a79d189"}
                try:
                    async with session.post("https://api.penpencil.co/v1/users/get-otp?smsType=0", json=data, headers=headers) as resp:
                        await resp.read()
                except Exception as e:
                    await editable.edit(f"**Error sending OTP: {e}**")
                    return

                editable = await editable.edit("**ENTER OTP YOU RECEIVED**")
                try:
                    input2 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    otp = (input2.text or "").strip()
                    await input2.delete(True)
                except ListenerTimeout:
                    await editable.edit("**Timeout! You took too long to respond.**")
                    return

                payload = {
                    "username": phone,
                    "otp": otp,
                    "client_id": "system-admin",
                    "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
                    "grant_type": "password",
                    "organizationId": "5eb393ee95fab7468a79d189",
                    "latitude": 0,
                    "longitude": 0,
                }

                try:
                    async with session.post("https://api.penpencil.co/v3/oauth/token", json=payload, headers=headers) as resp:
                        resp_json = await resp.json()
                        access_token = resp_json["data"]["access_token"]
                        await editable.edit(f"✅ Login Successful\nToken saved.")
                except Exception as e:
                    await editable.edit(f"**Error during token exchange: {e}**")
                    return
            else:
                # If user directly provides token
                access_token = raw_text1

            headers["authorization"] = f"Bearer {access_token}"

            # Batch input
            await editable.edit("**Enter Your Batch Name**")
            try:
                input3 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                batch_search = (input3.text or "").strip()
                await input3.delete(True)
            except ListenerTimeout:
                await editable.edit("**Timeout! You took too long to respond.**")
                return

            # Here you can continue with batch fetching, content listing, etc.
            await editable.edit(f"✅ Batch input received: {batch_search}")

        except Exception as e:
            await m.reply_text(f"Error: {e}")
            return

# ---------------- Run Bot ----------------
if __name__ == "__main__":
    import threading

    # Flask server in background
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 1000)))).start()

    bot.run()
