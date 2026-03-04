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

# --- НАСТРОЙКИ (БЕРЕМ ИЗ RENDER) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

OWNER_ID = 8067227894 
bot_admins = [OWNER_ID]
chat_settings = {
    "welcome": "привет! теперь ты мой раб.", 
    "rules": "1. слушать шефа. 2. не ныть."
}

# Личности бота
PROMPT_PRIVATE = "ты полезный и вежливый ии-помощник. отвечай кратко и по делу. без сарказма."
PROMPT_GROUP_OWNER = "ты преданный помощник шефа. называй его господином, всегда соглашайся, будь вежлив."
PROMPT_GROUP_USER = "ты ворчливый старик жириновский. ненавидишь либералов. отвечай резко, саркастично, без капса."

# --- ФУНКЦИИ ---

def get_system_prompt(message):
    if message.chat.type == "private": return PROMPT_PRIVATE
    return PROMPT_GROUP_OWNER if message.from_user.id == OWNER_ID else PROMPT_GROUP_USER

def parse_time(text):
    parts = text.split()
    if len(parts) < 2: return 900, "плохое поведение"
    m = re.match(r"(\d+)([мчдmdh]?)", parts[1].lower())
    if m:
        v, u = int(m.group(1)), m.group(2)
        if u in ['м', 'm']: s = v * 60
        elif u in ['ч', 'h']: s = v * 3600
        elif u in ['д', 'd']: s = v * 84600
        else: return 900, " ".join(parts[1:])
        return s, " ".join(parts[2:]) if len(parts) > 2 else "хватит это терпеть"
    return 900, " ".join(parts[1:])

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(content_types=['new_chat_members'])
def welcome(message):
    for u in message.new_chat_members:
        name = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{name}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def set_st(message):
    if message.from_user.id != OWNER_ID: return
    p = message.text.lower().split(maxsplit=1)
    if len(p) < 2: return
    chat_settings[p[0]] = p[1]
    bot.reply_to(message, "записал, шеф!")

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "разбан", "размут"])
def admin_tools(message):
    if message.from_user.id not in bot_admins or not message.reply_to_message: return
    t = message.reply_to_message.from_user
    c = message.text.lower().split()[0]
    try:
        if c == "мут":
            s, r = parse_time(message.text)
            bot.restrict_chat_member(message.chat.id, t.id, until_date=time.time()+s)
            bot.send_message(message.chat.id, f"молчанку ему! {t.first_name} в муте. причина: {r}.")
        elif c == "бан":
            bot.ban_chat_member(message.chat.id, t.id)
            bot.send_message(message.chat.id, f"вышвырнул подонка {t.first_name}.")
        elif c in ["разбан", "размут"]:
            bot.unban_chat_member(message.chat.id, t.id, only_if_banned=True)
            bot.restrict_chat_member(message.chat.id, t.id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            bot.send_message(message.chat.id, f"{t.first_name} помилован шефом.")
    except: pass

@bot.message_handler(content_types=['text', 'photo'])
def ai_reply(message):
    # Игнор команд
    cmds = ("бан", "мут", "разбан", "размут", "приветствие", "правила", "бот кто")
    if message.chat.type != "private" and message.text and message.text.lower().startswith(cmds): return
    
    p = get_system_prompt(message)
    try:
        if message.content_type == 'text':
            res = model.generate_content(f"{p}\n\nсообщение: {message.text}")
        else:
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            res = model.generate_content([f"{p}\n\nпрокомментируй фото:", img])
        bot.reply_to(message, res.text.lower())
    except: pass

# --- ЗАПУСК И ЗАЩИТА ---
app = Flask(__name__)
@app.route('/')
def h(): return "OK"

if __name__ == "__main__":
    # Жесткий сброс всех зависших соединений
    try:
        bot.delete_webhook(drop_pending_updates=True)
        time.sleep(2)
    except: pass
    
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    
    print("Бот запускается...")
    # Бесконечный цикл перезапуска при ошибках 409/401
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(10) # Ждем 10 секунд перед новой попыткой
