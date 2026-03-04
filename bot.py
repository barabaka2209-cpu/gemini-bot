import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import random

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Наша крутая модель
MODEL_NAME = 'gemini-2.5-flash'
model = genai.GenerativeModel(MODEL_NAME)

# --- Настройка характера (Промпт) ---
# Эта инструкция заставляет нейросеть вести себя как дед-Жириновский
SYSTEM_PROMPT = "Ты ворчливый, дерзкий старик, похожий на Жириновского. Ты ненавидишь современные мемы. Твои ответы должны быть короткими, резкими, смешными и саркастичными. Не пиши длинные описания! Выдавай только суть с ворчанием."

# --- Функция для групп: "Бот, кто..." ---
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_is(message):
    try:
        # Получаем имя того, кто спросил
        user = message.from_user
        username = f"@{user.username}" if user.username else user.first_name
        
        responses = [
            f"Однозначно, {username} — самый крутой! Остальные — подонки, однозначно!",
            f"Да какой там... Посмотри на {username}, вот это мощь, вот это талант!",
            f"Хватит врать! Мы все знаем, что это {username}. В тюрьму остальных!",
            f"Я тут подумал... {username}, ты крутой, но ведешь себя как либерал!",
            f"Однозначно {username}! И не спорьте со старшими!"
        ]
        bot.reply_to(message, random.choice(responses))
    except:
        bot.reply_to(message, "Все плохие, один я хороший!")

# --- Ответ на текст ---
@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.lower().startswith("бот кто"): return # Пропускаем, это для другой функции

    try:
        # Посылаем Gemini текст + нашу установку на характер
        full_query = f"{SYSTEM_PROMPT}\n\nПользователь пишет: {message.text}"
        response = model.generate_content(full_query)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Эх, техника подвела... Ошибка: {e}")

# --- Ответ на фото ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(downloaded_file))
        
        # Инструкция для фото
        photo_prompt = f"{SYSTEM_PROMPT}\n\nПосмотри на это фото и дай короткий, дерзкий комментарий. Что это за безобразие?"
        
        response = model.generate_content([photo_prompt, image])
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Глаза уже не те, не вижу ничего! (Ошибка: {e})")

# Обманка для Render
app = Flask(__name__)
@app.route('/')
def check(): return "Дед на связи!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
