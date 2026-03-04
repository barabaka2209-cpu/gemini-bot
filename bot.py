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
# Используем flash-модель для быстроты
model = genai.GenerativeModel('gemini-1.5-flash') 

OWNER_ID = 8067227894 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "1. слушать шефа. 2. не ныть."}

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "дед на связи. пиши, не стесняйся.")

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
    if message.chat.type == "private":
        p = "ты вежливый помощник. отвечай кратко."
    elif message.from_user.id == OWNER_ID:
        p = "ты преданный слуга шефа. называй его господином."
    else:
        p = "ты ворчливый старик жириновский. ругайся на либералов, отвечай едко, без капса."

    try:
        if message.content_type == 'text':
            if message.text.lower().startswith(("/", "бан", "мут")): return
            res = model.generate_content(f"{p}\n\nсообщение: {message.text}")
        else:
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            res = model.generate_content([f"{p}\n\nпрокомментируй фото:", img])
        bot.reply_to(message, res.text.lower())
    except Exception as e:
        print(f"ОШИБКА: {e}")

# --- ЗАПУСК ---
app = Flask(__name__)
@app.route('/')
def h(): return "OK"

def run_bot():
    # ЖЕСТКАЯ ОЧИСТКА ПЕРЕД СТАРТОМ
    while True:
        try:
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(5) # Большая пауза, чтобы убить конкурентов
            print("Слушаю эфир...")
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Конфликт или ошибка: {e}. Пробую снова через 10 сек...")
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    run_bot()
