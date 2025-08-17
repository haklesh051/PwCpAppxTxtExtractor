import requests
import asyncio
import aiohttp
import json
import zipfile
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import os
import base64
from pyrogram import Client, filters
import sys
import re
import requests
import uuid
import random
import string
import hashlib
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from pyromod import listen
from pyromod.exceptions.listener_timeout import ListenerTimeout
from pyrogram.types import Message
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import User, Message
from pyrogram.enums import ChatMemberStatus
from pyrogram.raw.functions.channels import GetParticipants
from config import api_id, api_hash, bot_token, auth_users
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
THREADPOOL = ThreadPoolExecutor(max_workers=1000)
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

image_list = [
"https://graph.org/file/8b1f4146a8d6b43e5b2bc-be490579da043504d5.jpg",
"https://graph.org/file/b75dab2b3f7eaff612391-282aa53538fd3198d4.jpg",
"https://graph.org/file/38de0b45dd9144e524a33-0205892dd05593774b.jpg",
"https://graph.org/file/be39f0eebb9b66d7d6bc9-59af2f46a4a8c510b7.jpg",
"https://graph.org/file/8b7e3d10e362a2850ba0a-f7c7c46e9f4f50b10b.jpg",
]
print(4321)
bot = Client(
    "bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token)

@bot.on_message(filters.command(["start"]))
async def start(bot, message):
  random_image_url = random.choice(image_list)

  keyboard = [
    [
      InlineKeyboardButton("🚀 Physics Wallah without Purchase 🚀", callback_data="pwwp")
    ],
    [
      InlineKeyboardButton("📘 Classplus without Purchase 📘", callback_data="cpwp")
    ],
    [
      InlineKeyboardButton("📒 Appx Without Purchase 📒", callback_data="appxwp")
    ]
  ]

  reply_markup = InlineKeyboardMarkup(keyboard)

  await message.reply_photo(
    photo=random_image_url,
    caption="**Developer - @pwextractowner\nPLEASE👇PRESS👇HERE**",
    quote=True,
    reply_markup=reply_markup
  )
@bot.on_message(group=2)
#async def account_login(bot: Client, m: Message):
#    try:
#        await bot.forward_messages(chat_id=chat_id, from_chat_id=m.chat.id, message_ids=m.id)
#    except:
#        pass
        
async def fetch_pwwp_data(session: aiohttp.ClientSession, url: str, headers: Dict = None, params: Dict = None, data: Dict = None, method: str = 'GET') -> Any:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.request(method, url, headers=headers, params=params, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"Attempt {attempt + 1} failed: aiohttp error fetching {url}: {e}")
        except Exception as e:
            logging.exception(f"Attempt {attempt + 1} failed: Unexpected error fetching {url}: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(90 ** attempt)
        else:
            logging.error(f"Failed to fetch {url} after {max_retries} attempts.")
            return None


async def process_pwwp_chapter_content(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, schedule_id, content_type, headers: Dict):
    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers=headers)
    content = []

    if data and data.get("success") and data.get("data"):
        data_item = data["data"]

        if content_type in ("videos", "DppVideos"):
            video_details = data_item.get('videoDetails', {})
            if video_details:
                name = data_item.get('topic', '')
                videoUrl = video_details.get('videoUrl') or video_details.get('embedCode') or ""
            #    image = video_details.get('image', "")

                if videoUrl:
                    line = f"{name}:{videoUrl}"
                    content.append(line)
               #     logging.info(line)

        elif content_type in ("notes", "DppNotes"):
            homework_ids = data_item.get('homeworkIds', [])
            for homework in homework_ids:
                attachment_ids = homework.get('attachmentIds', [])
                name = homework.get('topic', '')
                for attachment in attachment_ids:
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                    if url:
                        line = f"{name}:{url}"
                        content.append(line)
                    #    logging.info(line)

        return {content_type: content} if content else {}
    else:
        logging.warning(f"No Data Found For  Id - {schedule_id}")
        return {}


async def fetch_pwwp_all_schedule(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, content_type, headers: Dict) -> List[Dict]:
    all_schedule = []
    page = 1
    while True:
        params = {
            'tag': chapter_id,
            'contentType': content_type,
            'page': page
        }
        url = f"https://api.penpencil.co/v2/batches/{selected_batch_id}/subject/{subject_id}/contents"
        data = await fetch_pwwp_data(session, url, headers=headers, params=params)

        if data and data.get("success") and data.get("data"):
            for item in data["data"]:
                item['content_type'] = content_type
                all_schedule.append(item)
            page += 1
        else:
            break
    return all_schedule


async def process_pwwp_chapters(session: aiohttp.ClientSession, chapter_id, selected_batch_id, subject_id, headers: Dict):
    content_types = ['videos', 'notes', 'DppNotes', 'DppVideos']
    
    all_schedule_tasks = [fetch_pwwp_all_schedule(session, chapter_id, selected_batch_id, subject_id, content_type, headers) for content_type in content_types]
    all_schedules = await asyncio.gather(*all_schedule_tasks)
    
    all_schedule = []
    for schedule in all_schedules:
        all_schedule.extend(schedule)
        
    content_tasks = [
        process_pwwp_chapter_content(session, chapter_id, selected_batch_id, subject_id, item["_id"], item['content_type'], headers)
        for item in all_schedule
    ]
    content_results = await asyncio.gather(*content_tasks)

    combined_content = {}
    for result in content_results:
        if result:
            for content_type, content_list in result.items():
                if content_type not in combined_content:
                    combined_content[content_type] = []
                combined_content[content_type].extend(content_list)

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


async def process_pwwp_subject(session: aiohttp.ClientSession, subject: Dict, selected_batch_id: str, selected_batch_name: str, zipf: zipfile.ZipFile, json_data: Dict, all_subject_urls: Dict[str, List[str]], headers: Dict):
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

        for content_type in ['videos', 'notes', 'DppNotes', 'DppVideos']:
            if chapter_content.get(content_type):
                content = chapter_content[content_type]
                content.reverse()
                content_string = "\n".join(content)
                zipf.writestr(f"{subject_name}/{chapter_name}/{content_type}.txt", content_string.encode('utf-8'))
                json_data[selected_batch_name][subject_name][chapter_name][content_type] = content
                all_urls.extend(content)
    all_subject_urls[subject_name] = all_urls

def find_pw_old_batch(batch_search):

    try:
        response = requests.get(f"https://abhiguru143.github.io/AS-MULTIVERSE-PW/batch/batch.json")
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
        if batch_search.lower() in batch['batch_name'].lower():
            matching_batches.append(batch)

    return matching_batches

async def get_pwwp_todays_schedule_content_details(session: aiohttp.ClientSession, selected_batch_id, subject_id, schedule_id, headers: Dict) -> List[str]:

    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers)
    content = []

    if data and data.get("success") and data.get("data"):
        data_item = data["data"]
        
        video_details = data_item.get('videoDetails', {})
        if video_details:
            name = data_item.get('topic')
            
            videoUrl = video_details.get('videoUrl') or video_details.get('embedCode')
            image = video_details.get('image')
                
            if videoUrl:
                line = f"{name}:{videoUrl}\n"
                content.append(line)
           #     logging.info(line)
               
                          
        homework_ids = data_item.get('homeworkIds')
        for homework in homework_ids:
            attachment_ids = homework.get('attachmentIds')
            name = homework.get('topic')
            for attachment in attachment_ids:
            
                url = attachment.get('baseUrl', '') + attachment.get('key', '')
                        
                if url:
                    line = f"{name}:{url}\n"
                    content.append(line)
                #    logging.info(line)
                
        dpp = data_item.get('dpp')
        if dpp:
            dpp_homework_ids = dpp.get('homeworkIds')
            for homework in dpp_homework_ids:
                attachment_ids = homework.get('attachmentIds')
                name = homework.get('topic')
                for attachment in attachment_ids:
                
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                        
                    if url:
                        line = f"{name}:{url}\n"
                        content.append(line)
                    #    logging.info(line)
    else:
        logging.warning(f"No Data Found For  Id - {schedule_id}")
    return content
    
async def get_pwwp_all_todays_schedule_content(session: aiohttp.ClientSession, selected_batch_id: str, headers: Dict) -> List[str]:

    url = f"https://api.penpencil.co/v1/batches/{selected_batch_id}/todays-schedule"
    todays_schedule_details = await fetch_pwwp_data(session, url, headers)
    all_content = []

    if todays_schedule_details and todays_schedule_details.get("success") and todays_schedule_details.get("data"):
        tasks = []

        for item in todays_schedule_details['data']:
            schedule_id = item.get('_id')
            subject_id = item.get('batchSubjectId')
            
            task = asyncio.create_task(get_pwwp_todays_schedule_content_details(session, selected_batch_id, subject_id, schedule_id, headers))
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        
        for result in results:
            all_content.extend(result)
            
    else:
        logging.warning("No today's schedule data found.")

    return all_content
    
@bot.on_callback_query(filters.regex("^pwwp$"))
async def pwwp_callback(bot, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer()
    
    auth_user = auth_users[0]
    user = await bot.get_users(auth_user)
    owner_username = "@" + user.username

    if user_id not in auth_users:
        await bot.send_message(callback_query.message.chat.id, f"**You Are Not Subscribed To This Bot\nContact - {owner_username}**")
        return
            
    THREADPOOL.submit(asyncio.run, process_pwwp(bot, callback_query.message, user_id))

async def process_pwwp(bot: Client, m: Message, user_id: int):

    editable = await m.reply_text("**Enter Woking Access Token\n\nOR\n\nEnter Phone Number**")

    try:
        input1 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
        raw_text1 = input1.text
        await input1.delete(True)
    except:
        await editable.edit("**Timeout! You took too long to respond**")
        return

    headers = {
        'Host': 'api.penpencil.co',
        'client-id': '5eb393ee95fab7468a79d189',
        'client-version': '1910',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; M2101K6P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36',
        'randomid': '72012511-256c-4e1c-b4c7-29d67136af37',
        'client-type': 'WEB',
        'content-type': 'application/json; charset=utf-8',
    }

    loop = asyncio.get_event_loop()    
    CONNECTOR = aiohttp.TCPConnector(limit=1000, loop=loop)
    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        try:
            if raw_text1.isdigit() and len(raw_text1) == 10:
                phone = raw_text1
                data = {
                    "username": phone,
                    "countryCode": "+91",
                    "organizationId": "5eb393ee95fab7468a79d189"
                }
                try:
                    async with session.post(f"https://api.penpencil.co/v1/users/get-otp?smsType=0", json=data, headers=headers) as response:
                        await response.read()
                    
                except Exception as e:
                    await editable.edit(f"**Error : {e}**")
                    return

                editable = await editable.edit("**ENTER OTP YOU RECEIVED**")
                try:
                    input2 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    otp = input2.text
                    await input2.delete(True)
                except:
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
                    "longitude": 0
                }

                try:
                    async with session.post(f"https://api.penpencil.co/v3/oauth/token", json=payload, headers=headers) as response:
                        access_token = (await response.json())["data"]["access_token"]
                        monster = await editable.edit(f"<b>Physics Wallah Login Successful ✅</b>\n\n<pre language='Save this Login Token for future usage'>{access_token}</pre>\n\n")
                        editable = await m.reply_text("**Getting Batches In Your I'd**")
                    
                except Exception as e:
                    await editable.edit(f"**Error : {e}**")
                    return

            else:
                access_token = raw_text1
            
            headers['authorization'] = f"Bearer {access_token}"
        
            params = {
                'mode': '1',
                'page': '1',
            }
            try:
                async with session.get(f"https://api.penpencil.co/v3/batches/all-purchased-batches", headers=headers, params=params) as response:
                    response.raise_for_status()
                    batches = (await response.json()).get("data", [])
            except Exception as e:
                await editable.edit("**```\nLogin Failed❗TOKEN IS EXPIRED```\nPlease Enter Working Token\n                       OR\nLogin With Phone Number**")
                return
        
            await editable.edit("**Enter Your Batch Name**")
            try:
                input3 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                batch_search = input3.text
                await input3.delete(True)
            except:
                await editable.edit("**Timeout! You took too long to respond**")
                return
                
            url = f"https://api.penpencil.co/v3/batches/search?name={batch_search}"
            courses = await fetch_pwwp_data(session, url, headers)
            courses = courses.get("data", {}) if courses else {}

            if courses:
                text = ''
                for cnt, course in enumerate(courses):
                    name = course['name']
                    text += f"{cnt + 1}. ```\n{name}```\n"
                await editable.edit(f"**Send index number of the course to download.\n\n{text}\n\nIf Your Batch Not Listed Above Enter - No**")
            
                try:
                    input4 = await bot.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                    raw_text4 = input4.text
                    await input4.delete(True)
                except:
                    await editable.edit("**Timeout! You took too long to respond**")
                    return
                
                if input4.text.isdigit() and 1 <= int(input4.text) <= len(courses):
                    selected_course_index = int(input4.text.strip())
                    course = courses[selected_course_index - 1]
                    selected_batch_id = course['_id']
                    selected_batch_name = course['name']
                    clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")
                    clean_file_name = f"{user_id}_{clean_batch_name}"
                    
                elif "No" in input4.text:
                    courses = find_pw_old_batch(batch_search)
                    if courses:
                        text = ''
                        for cnt, course in enumerate(courses):
                            name = course['batch_name']
                            text += f"{cnt + 1}. ```\n{name}```\n"
                            
                        await editable.edit(f"*
