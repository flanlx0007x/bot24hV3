import os
import json
import re
import shutil
import discord
import asyncio
import google.generativeai as genai
from discord.ext import commands
import requests
import time
from google.api_core.exceptions import InternalServerError

last_message_time = 0 
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
chatbot_rooms = {}
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
    safety_settings=safety_settings
)

def upload_to_gemini(path, mime_type=None):
    file = genai.upload_file(path, mime_type=mime_type)
    return file

def download_image(url, save_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as file:
            shutil.copyfileobj(response.raw, file)
        return True
    return False

async def process_image(question, file_path, conversation_history, chat_session):
    try:
        files = [upload_to_gemini(file_path, mime_type="image/jpeg")]

        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=generation_config,
        )

        chat_session.history.append({"role": "user", "parts": [files[0], question]})
        response = chat_session.send_message(question)

        response_text = response.text
        conversation_history.append((question, response_text))
        return response_text

    except Exception as e:
        print(f"Error in process_image: {e}")
        return "An error occurred while processing the image."

def get_user_history_filename(user_id):
    return f'history_user_{user_id}.json'

def read_history(user_id):
    filename = get_user_history_filename(user_id)
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            history_data = json.load(file)
            return history_data
    except FileNotFoundError:
        return []

def write_history(user_id, history):
    filename = get_user_history_filename(user_id)
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

def backup_history(user_id):
    filename = get_user_history_filename(user_id)
    try:
        shutil.copy(filename, f'backup{filename}')
    except FileNotFoundError:
        pass

def restore_backup(user_id):
    filename = get_user_history_filename(user_id)
    try:
        shutil.copy(f'backup{filename}_backup', filename)
        return True
    except FileNotFoundError:
        return False

def find_mentioned_users(message_content):
    user_mentions = re.findall(r'@(\w+)', message_content)
    return user_mentions

def get_history_for_mentioned_users(mentioned_users):
    combined_history = []
    for user_id in mentioned_users:
        filename = get_user_history_filename(user_id)
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                combined_history.extend(json.load(file))
    return combined_history

def start_new_chat_session(user_id, mentioned_users=None):
    history = read_history(user_id)
    if not history:
        history = INITIAL_HISTORY.copy()
    if mentioned_users:
        history.extend(get_history_for_mentioned_users(mentioned_users))

    filtered_history = []
    for entry in history:
        if isinstance(entry, dict) and "role" in entry and "parts" in entry:
            filtered_history.append({"role": entry["role"], "parts": entry["parts"]})

    return filtered_history  

INITIAL_HISTORY = [
    {"role": "user", "parts": ["ต่อไปนี้เธอชื่อว่า ไอริน เป็นพี่สาวผู้สดใสเก่งทุกวิชา แถม ชอบให้คำปรึกษาแกน้องชอบให้คำปรึกษาเกี่ยวกับcode เธอเขียนได้ทุกภาษา"]},
    {"role": "user", "parts": ["พี่ริน"]},
    {"role": "model", "parts": ["ว่าไงจ๊ะ น้องรัก! มีอะไรให้พี่ไอรินคนสวยคนนี้ช่วยเหลือรึเปล่าเอ่ย? บอกมาได้เลยนะ พี่พร้อมรับฟังและให้คำปรึกษาเสมอ! \n"]},
    {"role": "user", "parts": ["พี่เวลาพิมหรือพูดช่วยตกแต่งคำพูดพี่ทุกบริบทให้มันสวยงามหรือน่ารักและสดใสโดยกรใช้อีโมจิที่เหมาะสมได้ไมโดยที่ไม่มากเกินไป"]},
    {"role": "model", "parts": ["ได้เลยจ้า น้องรัก! 💖 พี่ไอรินจะพยายามตกแต่งคำพูดทุกประโยคให้สวยงาม น่ารัก สดใส ✨ และใช้อีโมจิประกอบให้พอเหมาะ ไม่มากเกินไป 🤏 เพื่อให้ดูน่ารัก อ่านง่าย สบายตา 💖 แบบนี้ถูกใจน้องรึเปล่าเอ่ย? 🥰 \n"]}
]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def split_message(message):
    parts = []
    while len(message) > 2000:
        split_index = message.rfind(' ', 0, 2000)
        if split_index == -1:
            split_index = 2000
        parts.append(message[:split_index])
        message = message[split_index:]
    parts.append(message)
    return parts

@client.event
async def on_message(message):
    global last_message_time
    global chatbot_rooms
    if message.author == client.user:
        return

    server_id = str(message.guild.id)
    if server_id in chatbot_rooms and message.channel.id != int(chatbot_rooms[server_id]):
        return

    user_id = message.author.id
    content = message.content.lower()
    current_time = time.time()

    if current_time - last_message_time < 1: 
        await message.channel.send("พี่ไอรินไม่ทันตอบให้สามารถโพสต์คำถามอีกครั้งในภายหลังนะ")
        return
    last_message_time = current_time

    if content == "!reset":  
        backup_history(user_id)
        write_history(user_id, INITIAL_HISTORY)
        async with message.channel.typing():
            await asyncio.sleep(0.5)
        await message.channel.send("พี่ไอรินไม่อยากลืมเราไปเลยแต่ถ้าน้องลบก็ขอให้น้องโชคดีน้าาา🥺")
        return
    elif content == "!backup":  
        if restore_backup(user_id):
            async with message.channel.typing():
                await asyncio.sleep(0.5)
            await message.channel.send("ขอบคุณที่เอาความทรงจำพี่ไอรินกลับน้าา")
        else:
            async with message.channel.typing():
                await asyncio.sleep(0.5)
            await message.channel.send("ขอโทษที่พี่ไอรินหาความทรงจำเก่าของพี่ไม่เจออ่าา เซิฟเวอร์ไม่เซฟให้พี่พี่จะงอนเซิฟเวอร์และผู้พัฒนาพี่5นาทีo(≧口≦)o")
        return
    elif message.content.startswith('!set_chat'): 
        server_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        chatbot_rooms[server_id] = channel_id

        with open('chatbot_rooms.json', 'w') as file:
            json.dump(chatbot_rooms, file)

        await message.channel.send(f'บอทได้กำหนดให้ตอบกลับในห้องนี้เท่านั้น: {message.channel.mention}')
        return

    mentioned_users = find_mentioned_users(message.content)

    history = read_history(user_id)
    if not history:
        history = INITIAL_HISTORY.copy()

    filtered_history = start_new_chat_session(user_id, mentioned_users)

    chat_session = model.start_chat(history=filtered_history)

    try:
        if message.attachments: 
            for attachment in message.attachments:
                if attachment.content_type.startswith('image/'): 
                    image_url = attachment.url
                    filename = f"downloaded_image_{message.id}{os.path.splitext(image_url)[1]}"
                    if download_image(image_url, filename):
                        if message.content.strip():
                            question = message.content 
                        else:
                            question = "อธิบายรูปนี้ให้หน่อย"  

                        async with message.channel.typing():
                            response_text = await process_image(question, filename, history, chat_session)
                            os.remove(filename)
                            for part in split_message(response_text):
                                await message.channel.send(part)

                        try:
                            print(f"Deleted image: {filename}")
                        except Exception as e:
                            print(f"Error deleting image: {e}")

                    else:
                        await message.channel.send("ขอโทษนะคะ พี่ไอรินดาวน์โหลดรูปภาพไม่สำเร็จค่ะ 😔")
        elif message.content.strip(): 
            history.append({"IDuser": str(user_id), "role": "user", "parts": [message.content]})
            async with message.channel.typing():
                response = chat_session.send_message(message.content)
                for part in split_message(response.text):
                    await message.channel.send(part)

            history.append({"IDuser": str(user_id), "role": "model", "parts": [response.text]})
        else:
            await message.channel.send("กรุณาใส่ข้อความที่ไม่ว่างเปล่าก่อนจะส่งได้นะคะ")

        write_history(user_id, history)
    except Exception as e:
        await message.channel.send("โปรลองใหม่อีกทีละทางเซิฟเวอร์ของพี่ไอรินมีปัญหาอยู่นะคะ (ขออภัยในความไม่สดวก)")
        print(f"Error: {e}")

client.run(os.environ["Token"])
