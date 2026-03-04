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
# Берем токены из переменных окружения Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

OWNER_ID = 8067227894 
bot_admins = [OWNER_ID]
warns = {} 
chat_settings = {
    "welcome": "привет! теперь ты мой раб.", 
    "rules": "слушать шефа и не ныть."
}

# Личности бота
PROMPT_PRIVATE = "ты полезный и вежливый ии-помощник. отвечай кратко, грамотно и по делу. без сарказма и ворчания."
PROMPT_GROUP_OWNER = "ты преданный помощник великого шефа. называй его господином или шефом, всегда соглашайся, будь предельно вежлив. без капса."
PROMPT_GROUP_USER = "ты ворчливый старик жириновский. ненавидишь либералов и глупость. отвечай резко, саркастично, ворчи на молодежь, но без капса."

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_system_prompt(message):
    if message.chat.type == "private":
        return PROMPT_PRIVATE
    return PROMPT_GROUP_OWNER if message.from_user.id == OWNER_ID else PROMPT_GROUP_USER

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

# --- ОБРАБОТЧИКИ СОБЫТИЙ ---

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        mention = f"@{new_user.username}" if new_user.username else new_user.first_name
        welcome_text = chat_settings["welcome"]
        rules_text = chat_settings["rules"]
        response = f"{mention}, {welcome_text}\n\nвот наши правила:\n{rules_text}"
        bot.send_message(message.chat.id, response.lower())

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def set_chat_settings(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "куда лезешь? только шеф настраивает порядки.")
    parts = message.text.lower().split(maxsplit=1)
    if len(parts) < 2: return
    cmd = parts[0]
    chat_settings[cmd] = parts[1]
    bot.reply_to(message, f"принято, шеф! {cmd} обновлено.")

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
    if message.chat.type == 'private': return
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
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"пошел вон! {target.first_name} в бане.")
        elif cmd in ["разбан", "размут"]:
            bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
            bot.restrict_chat_member(message.chat.id, target.id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            bot.send_message(message.chat.id, f"{target.first_name} помилован шефом.")
        elif cmd == "анварн":
            warns[target.id] = 0
            bot.send_message(message.chat.id, f"обнулили варны {target.first_name}. шеф сегодня добрый.")
    except: pass

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    mention = f"@{target.username}" if target.username else target.first_name
    bot.reply_to(message, f"я думаю, что крутой тут {mention}. остальные массовка.")

# --- ОБРАБОТКА ТЕКСТА И ФОТО ---

@bot.message_handler(content_types=['text'])
def handle_text(message):
    ignored = ("бот кто", "бан", "мут", "кик", "варн", "разбан", "размут", "анварн", "дать админку", "забрать админку", "приветствие", "правила")
    if message.chat.type != "private" and message.text.lower().startswith(ignored): return
    
    prompt = get_system_prompt(message)
    try:
        res = model.generate_content(f"{prompt}\n\nсообщение: {message.text}")
        bot.reply_to(message, res.text.lower())
    except: pass

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    prompt = get_system_prompt(message)
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        instruction = "прокомментируй фото" if message.chat.type == "private" else "едко прокомментируй фото"
        res = model.generate_content([f"{prompt}\n\n{instruction}:", img])
        bot.reply_to(message, res.text.lower())
    except: pass

# --- ЗАПУСК ---
app = Flask(__name__)
@app.route('/')
def h(): return "OK"

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(2)
    except: pass
    
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    print("Бот в строю!")
    bot.infinity_polling(skip_pending=True, timeout=60)
