import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading

# Ключи подтянутся из настроек Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Я поменял модель на 'gemini-pro' - она самая стабильная и всегда работает
model = genai.GenerativeModel('gemini-pro')
# Для фото используем специальную модель vision
model_vision = genai.GenerativeModel('gemini-pro-vision')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.send_message(message.chat.id, "Думаю...")
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_message(message.chat.id, "Смотрю на фото...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(downloaded_file))
        
        prompt = message.caption if message.caption else "Что на фото?"
        # Используем модель vision для картинок
        response = model_vision.generate_content([prompt, image])
        bot.reply_to(message, response.text)
    except Exception as e:
        # Если vision модель капризничает, пробуем основную
        try:
            response = model.generate_content([prompt, image])
            bot.reply_to(message, response.text)
        except:
            bot.reply_to(message, f"Ошибка с фото: {e}")

app = Flask(__name__)
@app.route('/')
def keep_alive():
    return "OK"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
