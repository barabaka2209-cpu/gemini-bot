import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import random
import time
import re

# --- ПРОВЕРКА ТОКЕНА ---
# Если в Render не работает, временно вставь токен прямо сюда вместо os.environ.get
TOKEN_FROM_RENDER = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN_FROM_RENDER:
    print("ОШИБКА: Переменная TELEGRAM_TOKEN не найдена в настройках Render!")
    # Если совсем беда, можешь вставить токен текстом ниже для теста:
    # TOKEN_FROM_RENDER = "твой_токен_тут"

bot = telebot.TeleBot(TOKEN_FROM_RENDER)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

OWNER_ID = 8067227894 
bot_admins = [OWNER_ID]
warns = {} 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "слушать шефа и не ныть."}

SYSTEM_PROMPT_USER = "ты ворчливый старик жириновский. ненавидишь либералов. отвечай резко, саркастично, без капса."
SYSTEM_PROMPT_OWNER = "ты помощник шефа. называй его господином, всегда соглашайся, без капса."

# --- ЛОГИКА (ПРИВЕТСТВИЯ, МОДЕРАЦИЯ И Т.Д.) ---

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new(message):
    for u in message.new_chat_members:
        m = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{m}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def settings(message):
    if message.from_user.id != OWNER_ID: return
    p = message.text.lower().split(maxsplit=1)
    if len(p) < 2: return
    chat_settings[p[0].strip()] = p[1].strip()
    bot.reply_to(message, "записал, шеф!")

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "разбан", "размут", "анварн"])
def moderate(message):
    if message.from_user.id not in bot_admins: return
    if not message.reply_to_message: return
    t = message.reply_to_message.from_user
    cmd = message.text.lower().split()[0]
    try:
        if cmd == "мут":
            bot.restrict_chat_member(message.chat.id, t.id, until_date=time.time()+900)
            bot.send_message(message.chat.id, f"{t.first_name} в муте на 15 мин за плохое поведение.")
        elif cmd == "бан":
            bot.ban_chat_member(message.chat.id, t.id)
            bot.send_message(message.chat.id, f"{t.first_name} изгнан навсегда.")
        elif cmd in ["разбан", "размут"]:
            bot.unban_chat_member(message.chat.id, t.id, only_if_banned=True)
            bot.restrict_chat_member(message.chat.id, t.id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            bot.send_message(message.chat.id, f"{t.first_name} помилован шефом.")
    except Exception as e: print(f"Ошибка модерации: {e}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    mention = f"@{target.username}" if target.username else target.first_name
    bot.reply_to(message, f"я думаю, что крутой тут {mention}. остальные массовка.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    ignored = ("бот кто", "бан", "мут", "разбан", "размут", "анварн", "приветствие", "правила")
    if message.text.lower().startswith(ignored): return
    p = SYSTEM_PROMPT_OWNER if message.from_user.id == OWNER_ID else SYSTEM_PROMPT_USER
    try:
        res = model.generate_content(f"{p}\n\nсообщение: {message.text}")
        bot.reply_to(message, res.text.lower())
    except: pass

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    p = SYSTEM_PROMPT_OWNER if message.from_user.id == OWNER_ID else SYSTEM_PROMPT_USER
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        res = model.generate_content([f"{p}\n\nедко прокомментируй это без капса:", img])
        bot.reply_to(message, res.text.lower())
    except: pass

# --- ЗАПУСК ---
app = Flask(__name__)
@app.route('/')
def h(): return "дед онлайн"

if __name__ == "__main__":
    # Чистим старые сессии
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    
    print("Бот запускается...")
    bot.infinity_polling(skip_pending=True)
