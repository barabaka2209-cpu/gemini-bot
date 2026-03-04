import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask, request
from google.api_core import exceptions
import time

# --- 1. ТВОИ НАСТРОЙКИ ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = 8067227894 

# Собираем все ключи из настроек Render в один список (обойму)
def collect_keys():
    keys = []
    # Сначала основной ключ
    main_key = os.environ.get("GEMINI_API_KEY")
    if main_key: keys.append(main_key)
    
    # Потом все дополнительные GEMINI_API_KEY_1, _2 и т.д.
    for i in range(1, 11):
        extra_key = os.environ.get(f"GEMINI_API_KEY_{i}")
        if extra_key: keys.append(extra_key)
    return keys

API_KEYS = collect_keys()
current_key_idx = 0

bot = telebot.TeleBot(TOKEN)
chat_settings = {"welcome": "привет! теперь ты мой раб.", "rules": "1. слушать шефа. 2. не ныть."}

# --- 2. ЛОГИКА НЕЙРОНКИ ---
def ask_gemini(prompt_parts):
    global current_key_idx
    
    # Пытаемся спросить, перебирая ключи если нужно
    for _ in range(len(API_KEYS)):
        try:
            genai.configure(api_key=API_KEYS[current_key_idx])
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt_parts)
            return response.text
        except exceptions.ResourceExhausted:
            # Если лимит ключа исчерпан — крутим барабан
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            print(f"--- КЛЮЧ №{current_key_idx} ИСЧЕРПАН, МЕНЯЮ ---")
            continue 
        except Exception as e:
            return f"ошибка (ключ {current_key_idx}): {str(e)}"
            
    return "шеф, все ключи в обойме пусты! лимиты на сегодня всё."

# --- 3. ОБРАБОТЧИКИ ТЕЛЕГРАМ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"дед на связи! заряжено ключей: {len(API_KEYS)}. мозги: gemini 2.5 flash.")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_user(message):
    for u in message.new_chat_members:
        name = f"@{u.username}" if u.username else u.first_name
        bot.send_message(message.chat.id, f"{name}, {chat_settings['welcome']}\n\nправила:\n{chat_settings['rules']}".lower())

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    # Определяем роль
    if message.chat.type == "private":
        p = "ты вежливый и умный ии-помощник. отвечай кратко и только строчными буквами."
    elif message.from_user.id == OWNER_ID:
        p = "ты преданный слуга своего господина (owner_id 8067227894). называй его господином, будь очень почтителен."
    else:
        p = "ты ворчливый старик жириновский. ругайся на глупость вокруг, отвечай едко, без капса, только строчными буквами."

    try:
        if message.content_type == 'text':
            if message.text.lower().startswith(("/", "бан", "мут")): return
            ans = ask_gemini(f"{p}\n\nсообщение: {message.text}")
            bot.reply_to(message, ans.lower())
        
        elif message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
            ans = ask_gemini([f"{p}\n\nпрокомментируй фото:", img])
            bot.reply_to(message, ans.lower())
    except: pass

# --- 4. WEBHOOK СЕРВЕР ---
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
