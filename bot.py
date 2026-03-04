import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import random  # Для разнообразия в комментариях дедушки

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# СТАВИМ ТУ САМУЮ КРУТУЮ И НОВУЮ МОДЕЛЬ!
MODEL_NAME = 'gemini-2.5-flash'
model = genai.GenerativeModel(MODEL_NAME)


# --- Функция-обертка для создания «Души Дедушки» ---
# Список ворчливых комментариев дедушки, который не понимает мемы
grumpy_comments = [
    "Эх, в мое время все проще было... Ну да ладно, вот что я вижу:",
    "Что это за новомодная чепуха? Но коли просишь старого деда...",
    "Не понимаю я этих ваших картинок бессмысленных. Ладно, давай посмотрю:",
    "Слушай дедушку, внучок... Я тут пригляделся:",
    "И зачем это вообще нужно? Хмм. Но описание я дам:",
    "Ворчать неохота, но кто еще тебе правду скажет? Гляди:",
    "Вы все за какими-то зверями-мутантами гонитесь... Вот что я тебе скажу:"
]

def persona_wrap(text):
    """Принимает текст и добавляет к нему ворчливое дедушкино вступление."""
    # Случайным образом выбираем один комментарий из списка
    prefix = random.choice(grumpy_comments)
    return f"{prefix}\n\n{text}"


@bot.message_handler(commands=['models'])
def check_models(message):
    bot.send_message(message.chat.id, "Запрашиваю список моделей...")
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        reply_text = "✅ Доступные модели:\n\n" + "\n".join(available_models)
        reply_text += f"\n\nСейчас используется: {MODEL_NAME}"
        bot.reply_to(message, reply_text)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'):
        return
        
    # Мы УБРАЛИ строчку bot.send_message(message.chat.id, "Думаю...") !!!
    try:
        response = model.generate_content(message.text)
        # Обертываем ответ нейросети в «душу дедушки»
        bot.reply_to(message, persona_wrap(response.text))
    except Exception as e:
        bot.reply_to(message, f"Ошибка (текст): {e}")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    # Мы УБРАЛИ строчку bot.send_message(message.chat.id, "Изучаю фото...") !!!
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(downloaded_file))
        
        prompt = message.caption if message.caption else "Что на фото? Опиши подробно."
        
        response = model.generate_content([prompt, image])
        # Обертываем ответ нейросети в «душу дедушки»
        bot.reply_to(message, persona_wrap(response.text))
    except Exception as e:
        bot.reply_to(message, f"Ошибка (фото): {e}")


app = Flask(__name__)
@app.route('/')
def check():
    return "Бот работает на НОВОЙ модели и с НОВОЙ ДУШОЙ!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.infinity_polling()
