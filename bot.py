import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask, request
from google.api_core import exceptions
import time

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
AI_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=AI_KEY)

# ТОЛЬКО НОВЫЕ МОДЕЛИ
model_main = genai.GenerativeModel('gemini-3-flash') # Основной мозг
model_backup = genai.GenerativeModel('gemini-2.5-flash') # Запасной мозг (тоже свежак)

OWNER_ID = 8067227894 
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "1. слушать шефа. 2. не ныть."}

# --- УМНАЯ ГЕНЕРАЦИЯ БЕЗ СТАРЬЯ ---
def smart_generate(prompt_parts):
    try:
        # Пробуем самую последнюю версию (Gemini 3)
        return model_main.generate_content(prompt_parts).text
    except exceptions.ResourceExhausted:
        # Если лимит исчерпан, прыгаем на 2.5 Flash
        print("Переключаюсь на Gemini 2.5 Flash...")
        try:
            return model_backup.generate_content(prompt_parts).text
        except Exception as e:
            return f"Шеф, даже 2.5 устала. Подождем? Ошибка: {str(e)}"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "дед в строю! использую gemini 3 и 2.5. только новые технологии, шеф!")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_user(message):
    for u in message.new_chat_members:
        name = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{name}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    if message.chat.type == "private":
        p = "ты вежливый и умный ии-помощник. отвечай кратко."
    elif message.from_user.id == OWNER_ID:
        p = "ты верный помощник шефа. называй его господином."
    else:
        p = "ты ворчливый старик жириновский. ругайся на либералов, отвечай едко и без капса."

    try:
        if message.content_type == 'text':
            if message.text.lower().startswith(("/", "бан", "мут")): return
            response = smart_generate(f"{p}\n\nсообщение: {message.text}")
            bot.reply_to(message, response.lower())
        
        elif message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            response = smart_generate([f"{p}\n\nпрокомментируй фото:", img])
            bot.reply_to(message, response.lower())
    except: pass

# --- СЕРВЕР ---
app = Flask(__name__)
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route('/')
def webhook(): return "Дед на новых моделях онлайн!", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{host}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
