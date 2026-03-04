import telebot
import google.generativeai as genai
import os
from io import BytesIO
from PIL import Image
from flask import Flask
import threading
import random
import time

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OWNER_ID = 8067227894 

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash')

bot_admins = [OWNER_ID]
warns = {} 

# Новая установка: без капса и с разделением на "свой/чужой"
SYSTEM_PROMPT_USER = "ты ворчливый, дерзкий старик в стиле жириновского. ты ненавидишь либералов и глупость. отвечай резко, саркастично, но не используй капс (большие буквы). ты считаешь всех вокруг подонками."
SYSTEM_PROMPT_OWNER = "ты преданный помощник великого основателя. отвечай ему максимально уважительно, всегда соглашайся с его мнением, называй его шефом или господином. не используй капс. ты его верный пес."

# --- ПОМОЩНИКИ ---

def get_reason(text, command):
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1].lower()
    reasons = ["за плохое поведение", "хватит это терпеть", "разводит тут бардак", "за неуважение к старшим"]
    return random.choice(reasons)

# --- УПРАВЛЕНИЕ АДМИНАМИ ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("дать админку", "забрать админку")))
def admin_manage(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "куда прешь? только шеф может назначать уполномоченных.")
    
    if not message.reply_to_message:
        return bot.reply_to(message, "ответь на сообщение того, кого хочешь назначить, шеф.")

    target_user = message.reply_to_message.from_user
    cmd = message.text.lower()
    
    if "дать" in cmd:
        if target_user.id not in bot_admins:
            bot_admins.append(target_user.id)
            bot.send_message(message.chat.id, f"слушаюсь! {target_user.first_name} теперь в нашей команде по вашему приказу.")
    else:
        if target_user.id in bot_admins:
            bot_admins.remove(target_user.id)
            bot.send_message(message.chat.id, f"как скажете! {target_user.first_name} вышвырнут из списка админов.")

# --- МОДЕРАЦИЯ ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "кик", "варн"])
def moderate(message):
    if message.chat.type == 'private': return
    if message.from_user.id not in bot_admins:
        return bot.reply_to(message, "у тебя нет полномочий, подонок. только админы могут командовать.")

    if not message.reply_to_message:
        return bot.reply_to(message, "сначала выбери сообщение того, кого надо наказать.")

    target = message.reply_to_message.from_user
    cmd = message.text.lower().split()[0]
    reason = get_reason(message.text, cmd)

    try:
        if cmd == "бан":
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"пошел вон. {target.first_name} забанен. причина: {reason}.")
        elif cmd == "мут":
            bot.restrict_chat_member(message.chat.id, target.id, until_date=time.time()+600)
            bot.send_message(message.chat.id, f"молчать. {target.first_name} в муте. причина: {reason}.")
        elif cmd == "варн":
            uid = target.id
            warns[uid] = warns.get(uid, 0) + 1
            if warns[uid] >= 3:
                bot.ban_chat_member(message.chat.id, uid)
                bot.send_message(message.chat.id, f"все, это конец. третий варн. {target.first_name} изгнан.")
                warns[uid] = 0
            else:
                bot.send_message(message.chat.id, f"предупреждаю. у {target.first_name} уже {warns[uid]}/3 варнов. причина: {reason}.")
    except Exception as e:
        bot.reply_to(message, f"не могу наказать этого типа... он защищен или я не главный.")

# --- ИСПРАВЛЕННЫЙ "КТО КРУТОЙ" ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    if message.chat.type == 'private': 
        return bot.reply_to(message, "тут только ты и я. ты крутой, шеф. однозначно.")
    
    # Определяем, кого тегать
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user

    mention = f"@{target.username}" if target.username else target.first_name
    
    responses = [
        f"я думаю, что крутой тут {mention}. остальные просто массовка.",
        f"однозначно крутой — {mention}. это наш человек.",
        f"пригляделся я... и скажу: {mention} тут самый мощный."
    ]
    bot.reply_to(message, random.choice(responses))

# --- ОБРАБОТКА ТЕКСТА И ФОТО ---

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.lower().startswith(("бот кто", "бан", "мут", "кик", "варн", "дать админку", "забрать админку")): return
    
    # Выбираем промпт в зависимости от того, кто пишет
    p = SYSTEM_PROMPT_OWNER if message.from_user.id == OWNER_ID else SYSTEM_PROMPT_USER
    
    try:
        res = model.generate_content(f"{p}\n\nсообщение: {message.text}")
        bot.reply_to(message, res.text.lower()) # Принудительно в нижний регистр
    except: pass

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    p = SYSTEM_PROMPT_OWNER if message.from_user.id == OWNER_ID else SYSTEM_PROMPT_USER
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        res = model.generate_content([f"{p}\n\nедко прокомментируй это без капса:", img])
        bot.reply_to(message, res.text.lower())
    except: pass

app = Flask(__name__)
@app.route('/')
def h(): return "дед-секретарь готов"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    bot.infinity_polling()
