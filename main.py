import os
import re
import json
import time
import uuid
import base64
import random
import string
import zipfile
import hashlib
import logging
import asyncio
import aiohttp
import requests

from typing import Dict, List, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import Flask

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from pyrogram.errors import FloodWait

# Optional: pyromod for conversational inputs
from pyromod import listen
from pyromod.exceptions.listener_timeout import ListenerTimeout

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config / Credentials ---
# Try to use config.py if present; otherwise use ENV fallback
try:
    from config import api_id as CFG_API_ID, api_hash as CFG_API_HASH, bot_token as CFG_BOT_TOKEN, auth_users as CFG_AUTH_USERS
    API_ID = int(os.environ.get("API_ID", CFG_API_ID))
    API_HASH = os.environ.get("API_HASH", CFG_API_HASH)
    BOT_TOKEN = os.environ.get("BOT_TOKEN", CFG_BOT_TOKEN)
    auth_users = CFG_AUTH_USERS if isinstance(CFG_AUTH_USERS, (list, tuple, set)) else []
except Exception:
    API_ID = int(os.environ.get("API_ID", 24473318))
    API_HASH = os.environ.get("API_HASH", "e7dd0576c5ac0ff8f90971d6bb04c8f5")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8034069514:AAHUBpzSCq41jPwsJkDbXuEoVC_yCxzyuw0")
    # put your Telegram user IDs here who can use the bot
    auth_users = [6132794263]

# --- ThreadPool (if ever needed for CPU tasks) ---
THREADPOOL = ThreadPoolExecutor(max_workers=100)

# --- Flask (Render/Koyeb keep-alive) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    # Change port if your platform needs 8080
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "1000")))

# --- Bot Init ---
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UI Assets ---
image_list = [
    "https://graph.org/file/8b1f4146a8d6b43e5b2bc-be490579da043504d5.jpg",
    "https://graph.org/file/b75dab2b3f7eaff612391-282aa53538fd3198d4.jpg",
    "https://graph.org/file/38de0b45dd9144e524a33-0205892dd05593774b.jpg",
    "https://graph.org/file/be39f0eebb9b66d7d6bc9-59af2f46a4a8c510b7.jpg",
    "https://graph.org/file/8b7e3d10e362a2850ba0a-f7c7c46e9f4f50b10b.jpg",
]
print(4321)

# -------------- Helpers --------------

async def fetch_pwwp_data(
    session: aiohttp.ClientSession,
    url: str,
    headers: Dict = None,
    params: Dict = None,
    data: Dict = None,
    method: str = "GET",
) -> Any:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.request(method, url, headers=headers, params=params, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            logging.error(f"[{attempt+1}/{max_retries}] HTTP {e.status} fetching {url}: {e.message}")
        except aiohttp.ClientError as e:
            logging.error(f"[{attempt+1}/{max_retries}] aiohttp error fetching {url}: {e}")
        except Exception as e:
            logging.exception(f"[{attempt+1}/{max_retries}] Unexpected error fetching {url}: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    logging.error(f"Failed to fetch {url} after {max_retries} attempts.")
    return None


async def process_pwwp_chapter_content(
    session: aiohttp.ClientSession,
    chapter_id,
    selected_batch_id,
    subject_id,
    schedule_id,
    content_type,
    headers: Dict,
):
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers=headers)
    content = []

    if data and data.get("success") and data.get("data"):
        data_item = data["data"]

        if content_type in ("videos", "DppVideos"):
            video_details = data_item.get("videoDetails", {})
            if video_details:
                name = data_item.get("topic", "")
                videoUrl = video_details.get("videoUrl") or video_details.get("embedCode") or ""
                if videoUrl:
                    line = f"{name}:{videoUrl}"
                    content.append(line)

        elif content_type in ("notes", "DppNotes"):
            homework_ids = data_item.get("homeworkIds", [])
            for homework in homework_ids:
                attachment_ids = homework.get("attachmentIds", [])
                name = homework.get("topic", "")
                for attachment in attachment_ids:
                    url = (attachment.get("baseUrl", "") or "") + (attachment.get("key", "") or "")
                    if url:
                        line = f"{name}:{url}"
                        content.append(line)

        return {content_type: content} if content else {}
    else:
        logging.warning(f"No Data Found For Id - {schedule_id}")
        return {}


async def fetch_pwwp_all_schedule(
    session: aiohttp.ClientSession,
    chapter_id,
    selected_batch_id,
    subject_id,
    content_type,
    headers: Dict,
) -> List[Dict]:
    all_schedule = []
    page = 1
    while True:
        params = {"tag": chapter_id, "contentType": content_type, "page": page}
        url = f"https://api.penpencil.co/v2/batches/{selected_batch_id}/subject/{subject_id}/contents"
        data = await fetch_pwwp_data(session, url, headers=headers, params=params)

        if data and data.get("success") and data.get("data"):
            for item in data["data"]:
                item["content_type"] = content_type
                all_schedule.append(item)
            page += 1
        else:
            break
    return all_schedule


async def process_pwwp_chapters(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, headers: Dict):
    content_types = ["videos", "notes", "DppNotes", "DppVideos"]

    all_schedule_tasks = [
        fetch_pwwp_all_schedule(session, chapter_id, selected_batch_id, subject_id, content_type, headers)
        for content_type in content_types
    ]
    all_schedules = await asyncio.gather(*all_schedule_tasks)

    all_schedule = []
    for schedule in all_schedules:
        all_schedule.extend(schedule)

    content_tasks = [
        process_pwwp_chapter_content(
            session, chapter_id, selected_batch_id, subject_id, item["_id"], item["content_type"], headers
        )
        for item in all_schedule
    ]
    content_results = await asyncio.gather(*content_tasks)

    combined_content = {}
    for result in content_results:
        if result:
            for ctype, content_list in result.items():
                combined_content.setdefault(ctype, []).extend(content_list)

    return combined_content


async def get_pwwp_all_chapters(session: aiohttp.ClientSession, selected_batch_id, subject_id, headers: Dict):
    all_chapters = []
    page = 1
    while True:
        url = f"https://api.penpencil.co/v2/batches/{selected_batch_id}/subject/{subject_id}/topics?page={page}"
        data = await fetch_pwwp_data(session, url, headers=headers)

        if data and data.get("data"):
            chapters = data["data"]
            all_chapters.extend(chapters)
            page += 1
        else:
            break

    return all_chapters


async def process_pwwp_subject(
    session: aiohttp.ClientSession,
    subject: Dict,
    selected_batch_id: str,
    selected_batch_name: str,
    zipf: zipfile.ZipFile,
    json_data: Dict,
    all_subject_urls: Dict[str, List[str]],
    headers: Dict,
):
    subject_name = subject.get("subject", "Unknown Subject").replace("/", "-")
    subject_id = subject.get("_id")
    json_data[selected_batch_name][subject_name] = {}
    zipf.writestr(f"{subject_name}/", "")

    chapters = await get_pwwp_all_chapters(session, selected_batch_id, subject_id, headers)

    chapter_tasks = []
    for chapter in chapters:
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        zipf.writestr(f"{subject_name}/{chapter_name}/", "")
        json_data[selected_batch_name][subject_name][chapter_name] = {}

        chapter_tasks.append(process_pwwp_chapters(session, chapter["_id"], selected_batch_id, subject_id, headers))

    chapter_results = await asyncio.gather(*chapter_tasks)

    all_urls = []
    for chapter, chapter_content in zip(chapters, chapter_results):
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        for content_type in ["videos", "notes", "DppNotes", "DppVideos"]:
            if chapter_content.get(content_type):
                content = chapter_content[content_type]
                content.reverse()
                content_string = "\n".join(content)
                zipf.writestr(f"{subject_name}/{chapter_name}/{content_type}.txt", content_string.encode("utf-8"))
                json_data[selected_batch_name][subject_name][chapter_name][content_type] = content
                all_urls.extend(content)
    all_subject_urls[subject_name] = all_urls


def find_pw_old_batch(batch_search: str):
    try:
        response = requests.get("https://abhiguru143.github.io/AS-MULTIVERSE-PW/batch/batch.json", timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        return []

    matching_batches = []
    for batch in data:
        if batch_search.lower() in batch.get("batch_name", "").lower():
            matching_batches.append(batch)
    return matching_batches


async def get_pwwp_todays_schedule_content_details(
    session: aiohttp.ClientSession, selected_batch_id, subject_id, schedule_id, headers: Dict
) -> List[str]:
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers)
    content = []

    if data and data.get("success") and data.get("data"):
        data_item = data["data"]

        video_details = data_item.get("videoDetails", {})
        if video_details:
            name = data_item.get("topic")
            videoUrl = video_details.get("videoUrl") or video_details.get("embedCode")
            if videoUrl:
                content.append(f"{name}:{videoUrl}\n")

        homework_ids = data_item.get("homeworkIds", [])
        for homework in homework_ids:
            attachment_ids = homework.get("attachmentIds", [])
            name = homework.get("topic")
            for attachment in attachment_ids:
                url = (attachment.get("baseUrl", "") or "") + (attachment.get("key", "") or "")
                if url:
                    content.append(f"{name}:{url}\n")

        dpp = data_item.get("dpp")
        if dpp:
            dpp_homework_ids = dpp.get("homeworkIds", [])
            for homework in dpp_homework_ids:
                attachment_ids = homework.get("attachmentIds", [])
                name = homework.get("topic")
                for attachment in attachment_ids:
                    url = (attachment.get("baseUrl", "") or "") + (attachment.get("key", "") or "")
                    if url:
                        content.append(f"{name}:{url}\n")
    else:
        logging.warning(f"No Data Found For Id - {schedule_id}")
    return content


async def get_pwwp_all_todays_schedule_content(session: aiohttp.ClientSession, selected_batch_id: str, headers: Dict) -> List[str]:
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/todays-schedule"
    todays_schedule_details = await fetch_pwwp_data(session, url, headers)
    all_content = []

    if todays_schedule_details and todays_schedule_details.get("success") and todays_schedule_details.get("data"):
        tasks = []
        for item in todays_schedule_details["data"]:
            schedule_id = item.get("_id")
            subject_id = item.get("batchSubjectId")
            tasks.append(
                asyncio.create_task(
                    get_pwwp_todays_schedule_content_details(session, selected_batch_id, subject_id, schedule_id, headers)
                )
            )
        results = await asyncio.gather(*tasks)
        for result in results:
            all_content.extend(result)
    else:
        logging.warning("No today's schedule data found.")
    return all_content

# -------------- Bot Handlers --------------

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
    try:
        auth_owner = auth_users[0]
        user = await client.get_users(auth_owner)
        owner_username = "@" + (user.username or "owner")
    except Exception:
        owner_username = "@owner"

    if user_id not in auth_users:
        await client.send_message(
            callback_query.message.chat.id,
            f"**You Are Not Subscribed To This Bot\nContact - {owner_username}**",
        )
        return

    # run the flow directly (no asyncio.run inside)
    await process_pwwp(client, callback_query.message, user_id)

@bot.on_callback_query(filters.regex(r"^cpwp$"))
async def cpwp_callback(client: Client, callback_query):
    await callback_query.answer()
    await callback_query.message.reply_text("Classplus flow abhi wired nahi hai. (Stub)")

@bot.on_callback_query(filters.regex(r"^appxwp$"))
async def appxwp_callback(client: Client, callback_query):
    await callback_query.answer()
    await callback_query.message.reply_text("Appx flow abhi wired nahi hai. (Stub)")

# -------- Main PWWP Flow ----------

async def process_pwwp(client: Client, m: Message, user_id: int):
    editable = await m.reply_text("**Enter Working Access Token\n\nOR\n\nEnter Phone Number**")

    try:
        input1 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
        raw_text1 = (input1.text or "").strip()
        await input1.delete(True)
    except ListenerTimeout:
        await editable.edit("**Timeout! You took too long to respond**")
        return
    except Exception:
        await editable.edit("**Input error. Try again.**")
        return

    headers = {
        "Host": "api.penpencil.co",
        "client-id": "5eb393ee95fab7468a79d189",
        "client-version": "1910",
        "user-agent": "Mozilla/5.0 (Linux; Android 12; M2101K6P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36",
        "randomid": "72012511-256c-4e1c-b4c7-29d67136af37",
        "client-type": "WEB",
        "content-type": "application/json; charset=utf-8",
    }

    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            if raw_text1.isdigit() and len(raw_text1) == 10:
                phone = raw_text1
                data = {"username": phone, "countryCode": "+91", "organizationId": "5eb393ee95fab7468a79d189"}
                try:
                    async with session.post("https://api.penpencil.co/v1/users/get-otp?smsType=0", json=data, headers=headers) as resp:
                        await resp.read()
                except Exception as e:
                    await editable.edit(f"**Error while sending OTP: {e}**")
                    return

                editable = await editable.edit("**ENTER OTP YOU RECEIVED**")
                try:
                    input2 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    otp = (input2.text or "").strip()
                    await input2.delete(True)
                except ListenerTimeout:
                    await editable.edit("**Timeout! You took too long to respond**")
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
                    async with session.post("https://api.penpencil.co/v3/oauth/token", json=payload, headers=headers) as response:
                        resp_json = await response.json()
                        access_token = resp_json["data"]["access_token"]
                        await editable.edit(
                            f"<b>Physics Wallah Login Successful ✅</b>\n\n"
                            f"<pre language='Save this Login Token for future usage'>{access_token}</pre>\n\n"
                        )
                        editable = await m.reply_text("**Getting Batches In Your ID**")
                except Exception as e:
                    await editable.edit(f"**Error during token exchange: {e}**")
                    return
            else:
                access_token = raw_text1

            headers["authorization"] = f"Bearer {access_token}"

            params = {"mode": "1", "page": "1"}
            try:
                async with session.get("https://api.penpencil.co/v3/batches/all-purchased-batches", headers=headers, params=params) as response:
                    response.raise_for_status()
                    _ = (await response.json()).get("data", [])
            except Exception:
                await editable.edit(
                    "**```\nLogin Failed❗TOKEN IS EXPIRED```\nPlease Enter Working Token\n                       OR\nLogin With Phone Number**"
                )
                return

            await editable.edit("**Enter Your Batch Name**")
            try:
                input3 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                batch_search = (input3.text or "").strip()
                await input3.delete(True)
            except ListenerTimeout:
                await editable.edit("**Timeout! You took too long to respond**")
                return

            url = f"https://api.penpencil.co/v3/batches/search?name={batch_search}"
            courses_resp = await fetch_pwwp_data(session, url, headers)
            courses = courses_resp.get("data", []) if isinstance(courses_resp, dict) else []

            if courses:
                text = ""
                for cnt, course in enumerate(courses, start=1):
                    name = course.get("name", "Unnamed")
                    text += f"{cnt}. ```\n{name}```\n"
                await editable.edit(
                    f"**Send index number of the course to download.**\n\n{text}\n\nIf Your Batch Not Listed Above Enter - No"
                )

                try:
                    input4 = await client.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    raw_text4 = (input4.text or "").strip()
                    await input4.delete(True)
                e
