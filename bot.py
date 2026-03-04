import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading

# Берем ключи из Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# СТАВИМ НОВУЮ, КРУТУЮ И УМНУЮ МОДЕЛЬ!
MODEL_NAME = 'gemini-2.5-flash'
model = genai.GenerativeModel(MODEL_NAME)

@bot.message_handler(commands=['models'])
def check_models(message):
    bot.send_message(message.chat.id, "Запрашиваю у Google список разрешенных моделей...")
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        reply_text = "✅ Доступные модели:\n\n" + "\n".join(available_models)
        reply_text += f"\n\nСейчас бот использует: {MODEL_NAME}"
        bot.reply_to(message, reply_text)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'):
        return
        
    bot.send_message(message.chat.id, "Думаю...")
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка (текст): {e}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_message(message.chat.id, "Изучаю фото...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(downloaded_file))
        
        prompt = message.caption if message.caption else "Что на фото? Опиши подробно."
        response = model.generate_content([prompt, image])
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка (фото): {e}")

# Обманка для Render
app = Flask(__name__)
@app.route('/')
def check():
    return "Бот работает на новой модели!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
