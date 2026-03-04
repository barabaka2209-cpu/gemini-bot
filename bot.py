import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask, request
from google.api_core import exceptions
import time

# --- 1. НАСТРОЙКИ ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = 8067227894 

def collect_keys():
    found_keys = []
    # Сначала проверяем самый первый ключ (если он без цифры)
    k0 = os.environ.get("GEMINI_API_KEY")
    if k0: found_keys.append(k0)
    
    # Ищем ключи по твоему формату: GEMINI_API_KEY1, GEMINI_API_KEY2 ... до 15 штук
    for i in range(1, 16):
        k = os.environ.get(f"GEMINI_API_KEY{i}")
        if k:
            found_keys.append(k)
    return found_keys

API_KEYS = collect_keys()
current_key_idx = 0

bot = telebot.TeleBot(TOKEN)

# --- 2. ЛОГИКА ПЕРЕКЛЮЧЕНИЯ ---
def ask_gemini(prompt_parts):
    global current_key_idx
    
    if not API_KEYS:
        return "ошибка: шеф, я не вижу ключей! проверь названия в render (GEMINI_API_KEY1 и т.д.)"

    # Пробуем каждый ключ по кругу
    for attempt in range(len(API_KEYS)):
        try:
            # Берем ключ по текущему индексу
            genai.configure(api_key=API_KEYS[current_key_idx])
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            response = model.generate_content(prompt_parts)
            return response.text
            
        except exceptions.ResourceExhausted:
            # Лимит исчерпан — прыгаем на следующий ключ
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            print(f"--- КЛЮЧ №{current_key_idx} ИСЧЕРПАН, МЕНЯЮ ---")
            continue 
            
        except Exception as e:
            # Любая другая ошибка (неверный ключ и т.д.) — тоже пробуем следующий
            print(f"Ошибка на ключе {current_key_idx}: {str(e)}")
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            continue
            
    return f"шеф, все {len(API_KEYS)} ключа(ей) выдали лимит. нужно больше аккаунтов!"

# --- 3. ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"дед на связи! нашел ключей в обойме: {len(API_KEYS)}. модель: 2.5 flash.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    # Роли
    if message.chat.type == "private":
        p = "ты вежливый ии-помощник. отвечай кратко и строчными буквами."
    elif message.from_user.id == OWNER_ID:
        p = "ты преданный слуга шефа. называй его господином, будь почтителен."
    else:
        p = "ты ворчливый старик жириновский. ругайся на либералов, отвечай едко и без капса."

    try:
        if message.content_type == 'text':
            if message.text.lower().startswith(("/", "бан", "мут")): return
            ans = ask_gemini(f"{p}\n\nсообщение: {message.text}")
            bot.reply_to(message, ans.lower() if ans else "пустой ответ")
        
        elif message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            ans = ask_gemini([f"{p}\n\nпрокомментируй фото:", img])
            bot.reply_to(message, ans.lower() if ans else "пустой ответ")
    except Exception as e:
        print(f"Ошибка хендлера: {e}")

# --- 4. SERVER ---
app = Flask(__name__)
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route('/')
def webhook():
    return f"Дед в строю! Вижу ключей: {len(API_KEYS)}", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{host}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))# --- 4. WEBHOOK СЕРВЕР ---
app = Flask(__name__)

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def webhook_status():
    return f"Дед жив! Ключей в обойме: {len(API_KEYS)}", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"https://{host}/{TOKEN}")
        except: pass
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
