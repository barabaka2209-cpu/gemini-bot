import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading

# Эти данные бот сам возьмет из настроек Render (Environment Variables)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка бота и нейросети
bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Ответ на обычные текстовые сообщения
@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.send_message(message.chat.id, "Секунду, думаю...")
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

# Ответ на фотографии
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_message(message.chat.id, "Изучаю фото...")
    try:
        # Получаем файл фото
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(downloaded_file))
        
        # Если есть текст под фото - используем его, если нет - просто просим описать
        prompt = message.caption if message.caption else "Что на этом фото? Опиши подробно."
        
        response = model.generate_content([prompt, image])
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка при анализе фото: {e}")

# Техническая часть для работы на Render (чтобы бот не засыпал)
app = Flask(__name__)
@app.route('/')
def hello():
    return "Бот запущен и работает!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    # Запуск веб-сервера и бота одновременно
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
