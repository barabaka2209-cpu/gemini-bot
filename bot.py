import telebot
import os
import random
import time
import threading
import base64
from flask import Flask, request
from groq import Groq

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
OWNER_ID = 8067227894 

bot = telebot.TeleBot(TOKEN)
client = Groq(api_key=GROQ_KEY)
app = Flask(__name__)

PETER_IMAGES = ["https://i.postimg.cc/zV0Lqc8k/image.jpg"]
IMAGE_CHANCE = 10 

def ask_ai(prompt_text, system_prompt):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt_text}],
            temperature=0.8,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Ошибка текста: {e}")
        return "мои мозги сейчас в отключке."

def ask_ai_vision(image_bytes, system_prompt):
    """Функция для анализа фото через Vision-модель Groq"""
    try:
        # Кодируем картинку в base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview", # Специальная модель для фото
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{system_prompt}\n\nпрокомментируй это фото:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Ошибка Vision: {e}")
        return "я ослеп! это даже хуже чем тот раз когда я смотрел на сварку без маски."

def process_logic(message):
    try:
        # Промпт Питера
        if message.chat.type == "private":
            p = "ты вежливый ии-помощник. отвечай кратко и строго строчными буквами."
        elif message.from_user.id == OWNER_ID:
            p = "ты преданный слуга своего господина. называй его господином. пиши строго строчными буквами."
        else:
            p = ("ты питер гриффин. ты ворчливый, ленивый и глуповатый. "
                 "постоянно шути, используй 'это даже хуже, чем тот раз, когда я...'. "
                 "отвечай едко и СТРОГО строчными буквами.")

        # ОБРАБОТКА ТЕКСТА
        if message.content_type == 'text':
            text_lower = message.text.lower()
            if text_lower in ["правила", "/rules"]:
                bot.reply_to(message, "мои правила: я босс, ты нет. свободен.")
                return

            bot.send_chat_action(message.chat.id, 'typing')
            ans = ask_ai(message.text, p)
            bot.reply_to(message, ans.lower() if ans else "пусто")

        # ОБРАБОТКА ФОТО
        elif message.content_type == 'photo':
            bot.send_chat_action(message.chat.id, 'typing')
            
            # Получаем файл
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Отправляем в Vision модель
            ans = ask_ai_vision(downloaded_file, p)
            bot.reply_to(message, ans.lower() if ans else "ничего не вижу")

    except Exception as e:
        print(f"Ошибка обработки: {e}")

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    threading.Thread(target=process_logic, args=(message,)).start()

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "ok", 200

@app.route('/')
def webhook(): return "Питер видит и слышит!", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{host}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
