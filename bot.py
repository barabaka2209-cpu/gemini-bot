import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import time

# --- НАСТРОЙКИ ---
# Если Render все еще выдает 401, замени строку ниже на: TELEGRAM_TOKEN = "ТВОЙ_ТОКЕН_ТУТ"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

OWNER_ID = 8067227894 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "слушать шефа и не ныть."}

# Профили личности
PROMPT_PRIVATE = "ты полезный и вежливый ии-помощник. отвечай кратко, грамотно и по делу. без сарказма."
PROMPT_GROUP_OWNER = "ты преданный помощник шефа. называй его господином, всегда соглашайся, будь вежлив, без капса."
PROMPT_GROUP_USER = "ты ворчливый старик жириновский. ненавидишь либералов, ворчишь на молодежь. отвечай резко, саркастично, без капса."

# --- ЛОГИКА ОПРЕДЕЛЕНИЯ КТО ПИШЕТ ---
def get_system_prompt(message):
    if message.chat.type == "private":
        return PROMPT_PRIVATE
    else: # Если это группа или супергруппа
        if message.from_user.id == OWNER_ID:
            return PROMPT_GROUP_OWNER
        else:
            return PROMPT_GROUP_USER

# --- ПРИВЕТСТВИЯ ---
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new(message):
    for u in message.new_chat_members:
        m = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{m}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

# --- НАСТРОЙКИ (ТОЛЬКО ДЛЯ ВАС) ---
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("приветствие", "правила")))
def settings(message):
    if message.from_user.id != OWNER_ID: return
    p = message.text.lower().split(maxsplit=1)
    if len(p) < 2: return
    chat_settings[p[0].strip()] = p[1].strip()
    bot.reply_to(message, "записал, шеф!")

# --- ОБРАБОТКА ТЕКСТА ---
@bot.message_handler(content_types=['text'])
def handle_text(message):
    # Игнорируем команды модерации в группах, чтобы не путать с текстом
    ignored = ("бан", "мут", "разбан", "размут", "бот кто", "приветствие", "правила")
    if message.chat.type != "private" and message.text.lower().startswith(ignored):
        return 

    prompt = get_system_prompt(message)
    try:
        res = model.generate_content(f"{prompt}\n\nсообщение от пользователя: {message.text}")
        bot.reply_to(message, res.text.lower())
    except Exception as e:
        print(f"Ошибка Gemini: {e}")

# --- ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    prompt = get_system_prompt(message)
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        # Добавляем контекст для фото в зависимости от личности
        instruction = "прокомментируй это фото" if message.chat.type == "private" else "едко прокомментируй это фото"
        res = model.generate_content([f"{prompt}\n\n{instruction}:", img])
        bot.reply_to(message, res.text.lower())
    except Exception as e:
        print(f"Ошибка фото: {e}")

# --- ЗАПУСК ---
app = Flask(__name__)
@app.route('/')
def h(): return "бот работает"

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    print("Дед (и помощник) выходит на связь...")
    bot.infinity_polling(skip_pending=True)
