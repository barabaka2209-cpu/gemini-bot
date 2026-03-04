import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import time

# --- КОНФИГ ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
AI_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # Используем 1.5 для стабильности

OWNER_ID = 8067227894 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "1. слушать шефа. 2. не ныть."}

# --- ЛОГИКА ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "дед на связи. в личке я помощник, в группе — гроза либералов.")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_user(message):
    for u in message.new_chat_members:
        name = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{name}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def set_cfg(message):
    if message.from_user.id != OWNER_ID: return
    p = message.text.lower().split(maxsplit=1)
    if len(p) < 2: return
    chat_settings[p[0]] = p[1]
    bot.reply_to(message, "записал, шеф!")

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    # Определяем роль
    if message.chat.type == "private":
        prompt = "ты вежливый помощник ии. отвечай кратко."
    elif message.from_user.id == OWNER_ID:
        prompt = "ты преданный слуга шефа. называй его господином."
    else:
        prompt = "ты ворчливый старик жириновский. ругайся на либералов, отвечай едко и саркастично, без капса."

    try:
        if message.content_type == 'text':
            # Игнорируем команды модерации
            if message.text.lower().startswith(("бан", "мут", "разбан", "бот кто")): return
            response = model.generate_content(f"{prompt}\n\nсообщение: {message.text}")
        else:
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            response = model.generate_content([f"{prompt}\n\nпрокомментируй фото:", img])
        
        bot.reply_to(message, response.text.lower())
    except Exception as e:
        print(f"ОШИБКА GEMINI: {e}")
        # Если нейронка сбоит, бот хотя бы подаст знак
        if message.chat.type == "private":
            bot.reply_to(message, "шеф, нейронка тупит. проверьте логи в render.")

# --- ЗАПУСК ---
app = Flask(__name__)
@app.route('/')
def h(): return "OK"

if __name__ == "__main__":
    try:
        bot.delete_webhook(drop_pending_updates=True)
        time.sleep(2)
    except: pass
    
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    
    print("БОТ ЗАПУЩЕН И СЛУШАЕТ...")
    bot.infinity_polling(skip_pending=True)
