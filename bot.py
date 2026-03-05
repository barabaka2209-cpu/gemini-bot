import telebot
import google.generativeai as genai
import os
import random
from io import BytesIO
from PIL import Image
from flask import Flask, request
from google.api_core import exceptions
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = 8067227894 

# === ТВОЯ ТЕСТОВАЯ КАРТИНКА (прямая ссылка) ===
TEST_IMAGE = "https://i.postimg.cc/zV0Lqc8k/image.jpg"

# === СПИСОК КАРТИНОК ДЛЯ РАНДОМА (Пока тут только одна, потом добавишь ID) ===
PETER_IMAGES = [
    TEST_IMAGE
]

# Шанс рандомной отправки картинки (15%)
IMAGE_CHANCE = 15 

def collect_keys():
    found_keys = []
    k0 = os.environ.get("GEMINI_API_KEY")
    if k0: found_keys.append(k0)
    for i in range(1, 16):
        k = os.environ.get(f"GEMINI_API_KEY{i}")
        if k: found_keys.append(k)
    return found_keys

API_KEYS = collect_keys()
current_key_idx = 0
bot = telebot.TeleBot(TOKEN)

def ask_gemini(prompt_parts):
    global current_key_idx
    if not API_KEYS: return "ошибка: нет ключей."
    for _ in range(len(API_KEYS)):
        try:
            genai.configure(api_key=API_KEYS[current_key_idx])
            model = genai.GenerativeModel('gemini-2.5-flash')
            return model.generate_content(prompt_parts).text
        except exceptions.ResourceExhausted:
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            continue 
        except Exception:
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            continue
    return "шеф, все ключи пусты."

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"хехехе, питер гриффин на связи. ключей: {len(API_KEYS)}.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    # === РОЛИ ===
    if message.chat.type == "private":
        p = "ты вежливый ии-помощник. отвечай кратко и строго строчными буквами."
    elif message.from_user.id == OWNER_ID:
        p = "ты преданный слуга своего господина. называй его господином, будь почтителен. пиши строго строчными буквами."
    else:
        p = (
            "ты питер гриффин из гриффинов. ты ворчливый, ленивый и глуповатый. "
            "постоянно шути над собеседником, насмехайся над ним. "
            "используй абсурдные вставки в стиле 'это даже хуже, чем тот раз, когда я...'. "
            "отвечай едко, без уважения и СТРОГО строчными буквами."
        )

    try:
        # === ОБРАБОТКА ТЕКСТА ===
        if message.content_type == 'text':
            text_lower = message.text.lower()
            if text_lower.startswith(("/", "бан", "мут")): return

            # 🛑 ПРОВЕРКА НА КОДОВОЕ СЛОВО "КАРТИНКА" 🛑
            if text_lower == "картинка":
                bot.send_photo(
                    message.chat.id, 
                    TEST_IMAGE, 
                    caption="хехехе, вот твоя тестовая картинка!", 
                    reply_to_message_id=message.message_id
                )
                return # Выходим, чтобы не дергать нейросеть

            # Если не кодовое слово - отвечает нейросеть
            ans = ask_gemini(f"{p}\n\nсообщение: {message.text}")
            final_text = ans.lower() if ans else "пустой ответ"

            # Рандомайзер картинок (шанс IMAGE_CHANCE)
            is_random_image_time = random.randint(1, 100) <= IMAGE_CHANCE
            if is_random_image_time and message.chat.type != "private":
                random_img_url = random.choice(PETER_IMAGES)
                bot.send_photo(message.chat.id, random_img_url, caption=final_text[:1024], reply_to_message_id=message.message_id)
            else:
                bot.reply_to(message, final_text)

        # === ОБРАБОТКА ФОТО ===
        elif message.content_type == 'photo':
            file_id = message.photo[-1].file_id # Получаем ID картинки
            
            # 🛠 ЕСЛИ ТЫ (ХОЗЯИН) КИНУЛ ФОТО - БОТ ВЫДАСТ ЕГО ID 🛠
            if message.from_user.id == OWNER_ID:
                bot.reply_to(message, f"Код этой картинки для списка (скопируй):\n`{file_id}`", parse_mode="Markdown")

            # Скачиваем фото и отправляем нейросети
            file_info = bot.get_file(file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            ans = ask_gemini([f"{p}\n\nпрокомментируй фото:", img])
            bot.reply_to(message, ans.lower() if ans else "пустой ответ")

    except Exception as e:
        print(f"Ошибка: {e}")

app = Flask(__name__)
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route('/')
def webhook(): return f"Питер в строю! Ключей: {len(API_KEYS)}", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{host}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
