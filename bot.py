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

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OWNER_ID = 8067227894 

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash')

# Временные настройки (сбросятся при перезагрузке Render)
bot_admins = [OWNER_ID]
warns = {} 
chat_settings = {
    "welcome": "добро пожаловать в наш лагерь!",
    "rules": "правил пока нет, но веди себя прилично."
}

SYSTEM_PROMPT_USER = "ты ворчливый старик в стиле жириновского. ненавидишь либералов. отвечай резко, саркастично, без капса."
SYSTEM_PROMPT_OWNER = "ты преданный помощник шефа. отвечай ему уважительно, всегда соглашайся, без капса."

# --- ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ ---

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        mention = f"@{new_user.username}" if new_user.username else new_user.first_name
        welcome_text = chat_settings["welcome"]
        rules_text = chat_settings["rules"]
        
        response = f"{mention}, {welcome_text}\n\nвот наши правила:\n{rules_text}"
        bot.send_message(message.chat.id, response.lower())

# --- НАСТРОЙКА ПРАВИЛ И ПРИВЕТСТВИЙ (ТОЛЬКО ДЛЯ ШЕФА) ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def set_chat_settings(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "куда лезешь? только шеф настраивает порядки.")
    
    text = message.text.lower()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        return bot.reply_to(message, "шеф, напишите после команды сам текст, который нужно запомнить.")
    
    cmd = parts[0]
    content = parts[1]
    
    if cmd == "приветствие":
        chat_settings["welcome"] = content
        bot.reply_to(message, "принято, шеф! теперь буду встречать новичков именно так.")
    elif cmd == "правила":
        chat_settings["rules"] = content
        bot.reply_to(message, "записал! правила теперь жесткие, как вы любите.")

# --- УМНЫЙ ПАРСЕР ВРЕМЕНИ ---

def parse_ban_time(text):
    parts = text.split()
    if len(parts) < 2: return 900, "за плохое поведение"
    time_str = parts[1]
    reason = " ".join(parts[2:]) if len(parts) > 2 else "хватит это терпеть"
    match = re.match(r"(\d+)([мчдmdh]?)", time_str.lower())
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit in ['м', 'm']: s = val * 60
        elif unit in ['ч', 'h']: s = val * 3600
        elif unit in ['д', 'd']: s = val * 86400
        else: return 900, " ".join(parts[1:])
        return s, reason
    return 900, " ".join(parts[1:])

# --- МОДЕРАЦИЯ И АДМИНКА ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("дать админку", "забрать админку")))
def admin_manage(message):
    if message.from_user.id != OWNER_ID: return
    if not message.reply_to_message: return
    target = message.reply_to_message.from_user
    if "дать" in message.text.lower():
        if target.id not in bot_admins: bot_admins.append(target.id)
        bot.send_message(message.chat.id, f"слушаюсь! {target.first_name} теперь в команде.")
    else:
        if target.id in bot_admins: bot_admins.remove(target.id)
        bot.send_message(message.chat.id, f"как скажете! {target.first_name} вышвырнут.")

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "кик", "варн", "разбан", "размут", "анварн"])
def moderate(message):
    if message.from_user.id not in bot_admins: return
    if not message.reply_to_message: return
    target = message.reply_to_message.from_user
    cmd = message.text.lower().split()[0]
    try:
        if cmd == "мут":
            s, r = parse_ban_time(message.text)
            bot.restrict_chat_member(message.chat.id, target.id, until_date=time.time()+s)
            bot.send_message(message.chat.id, f"молчанку ему! {target.first_name} в муте. причина: {r}.")
        elif cmd == "бан":
            _, r = parse_ban_time(message.text)
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"пошел вон! {target.first_name} в бане. причина: {r}.")
        elif cmd == "анварн":
            warns[target.id] = 0
            bot.send_message(message.chat.id, f"обнулили варны {target.first_name}. шеф добрый сегодня.")
    except: pass

# --- КТО КРУТОЙ ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    mention = f"@{target.username}" if target.username else target.first_name
    bot.reply_to(message, f"я думаю, что крутой тут {mention}. остальные массовка.")

# --- ТЕКСТ И ФОТО ---

@bot.message_handler(content_types=['text'])
def handle_text(message):
    # Команды, которые бот не должен обрабатывать как обычный текст
    ignored = ("бот кто", "бан", "мут", "кик", "варн", "разбан", "размут", "анварн", "дать админку", "забрать админку", "приветствие", "правила")
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

app = Flask(__name__)
@app.route('/')
def h(): return "OK"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    bot.infinity_polling()
