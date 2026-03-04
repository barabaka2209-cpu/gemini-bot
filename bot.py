import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask, request
import time

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
AI_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

OWNER_ID = 8067227894 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "1. слушать шефа. 2. не ныть."}

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "дед на связи. готов служить, шеф!")

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
        # ТЕПЕРЬ ОН НЕ БУДЕТ МОЛЧАТЬ!
        bot.reply_to(message, f"Шеф, нейронка отвалилась! Ошибка: {str(e)}")

# --- WEBHOOK (БРОНЯ ОТ ОШИБОК) ---
app = Flask(__name__)

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def webhook():
    return "Дед жив!", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"https://{host}/{TOKEN}")
        except: pass
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
