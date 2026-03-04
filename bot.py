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

SYSTEM_PROMPT_USER = "ты ворчливый, дерзкий старик в стиле жириновского. ты ненавидишь либералов и глупость. отвечай резко, саркастично, но не используй капс. ты считаешь всех вокруг подонками."
SYSTEM_PROMPT_OWNER = "ты преданный помощник великого основателя. отвечай ему максимально уважительно, всегда соглашайся с его мнением, называй его шефом или господином. не используй капс."

# --- ПОМОЩНИКИ ---

def get_reason(text, command):
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1].lower()
    reasons = ["за плохое поведение", "хватит это терпеть", "разводит тут бардак"]
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

# --- МОДЕРАЦИЯ (НАКАЗАНИЯ И ПОМИЛОВАНИЯ) ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "кик", "варн", "анбан", "разбан", "анмут", "размут", "анварн"])
def moderate(message):
    if message.chat.type == 'private': return
    if message.from_user.id not in bot_admins:
        return bot.reply_to(message, "у тебя нет полномочий. только админы могут распоряжаться судьбами.")

    if not message.reply_to_message:
        return bot.reply_to(message, "сначала выбери сообщение того, с кем будем разбираться.")

    target = message.reply_to_message.from_user
    cmd = message.text.lower().split()[0]
    reason = get_reason(message.text, cmd)

    try:
        # Наказания
        if cmd == "бан":
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"пошел вон. {target.first_name} забанен. причина: {reason}.")
        elif cmd == "мут":
            bot.restrict_chat_member(message.chat.id, target.id, until_date=time.time()+600)
            bot.send_message(message.chat.id, f"молчать. {target.first_name} в муте. причина: {reason}.")
        elif cmd == "кик":
            bot.unban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"выставили за дверь. {target.first_name} кикнут.")
        elif cmd == "варн":
            uid = target.id
            warns[uid] = warns.get(uid, 0) + 1
            if warns[uid] >= 3:
                bot.ban_chat_member(message.chat.id, uid)
                bot.send_message(message.chat.id, f"третий варн. {target.first_name} изгнан за систематические нарушения.")
                warns[uid] = 0
            else:
                bot.send_message(message.chat.id, f"предупреждаю. у {target.first_name} теперь {warns[uid]}/3 варнов.")

        # Помилования (АН-команды)
        elif cmd in ["анбан", "разбан"]:
            bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
            bot.send_message(message.chat.id, f"так и быть, путь свободен. {target.first_name} разбанен.")
        elif cmd in ["анмут", "размут"]:
            bot.restrict_chat_member(message.chat.id, target.id, 
                can_send_messages=True, can_send_media_messages=True, 
                can_send_other_messages=True, can_add_web_page_previews=True)
            bot.send_message(message.chat.id, f"говори, чего уж там. {target.first_name} размучен.")
        elif cmd == "анварн":
            warns[target.id] = 0
            bot.send_message(message.chat.id, f"счетчик обнулен. {target.first_name}, считай, что тебе повезло. 0/3 варнов.")

    except Exception as e:
        bot.reply_to(message, f"не вышло. либо он админ, либо я не имею прав в этой группе.")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    if message.chat.type == 'private': 
        return bot.reply_to(message, "тут только мы. вы вне конкуренции, шеф.")
    
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    mention = f"@{target.username}" if target.username else target.first_name
    
    responses = [
        f"я думаю, что крутой тут {mention}. остальные — массовка.",
        f"однозначно крутой — {mention}. это наш человек.",
        f"глянул я внимательно... {mention} тут самый мощный."
    ]
    bot.reply_to(message, random.choice(responses))

@bot.message_handler(content_types=['text'])
def handle_text(message):
    # список команд, которые не должна перехватывать нейронка
    cmds = ("бот кто", "бан", "мут", "кик", "варн", "анбан", "разбан", "анмут", "размут", "анварн", "дать админку", "забрать админку")
    if message.text.lower().startswith(cmds): return
    
    p = SYSTEM_PROMPT_OWNER if message.from_user.id == OWNER_ID else SYSTEM_PROMPT_USER
    try:
        res = model.generate_content(f"{p}\n\nсообщение: {message.text}")
        bot.reply_to(message, res.text.lower())
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
