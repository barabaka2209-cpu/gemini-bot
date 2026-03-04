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
OWNER_ID = 8067227894  # ТВОЙ АЙДИ ВСТАВЛЕН!

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash')

# Временные базы (сбросятся при перезагрузке Render)
bot_admins = [OWNER_ID]
warns = {} 

SYSTEM_PROMPT = "Ты ворчливый, дерзкий старик, похожий на Жириновского. Ты ненавидишь либералов и нарушителей порядка. Ответы короткие, резкие, с криками. Ты не терпишь возражений!"

# --- ПОМОЩНИКИ ---

def get_reason(text, command):
    """Извлекает причину из сообщения или придумывает её"""
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1]
    
    reasons = [
        "за плохое поведение!", "хватит это терпеть!", 
        "либеральные замашки!", "потому что я так сказал!",
        "разводит тут бардак!", "в тюрьму его!", "за неуважение к старшим!"
    ]
    return random.choice(reasons)

# --- УПРАВЛЕНИЕ АДМИНАМИ БОТА ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith(("дать админку", "забрать админку")))
def admin_manage(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "Куда прешь? Только ГЛАВНЫЙ может назначать уполномоченных! Однозначно!")
    
    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    
    if not target_user:
        return bot.reply_to(message, "Ответь этой командой на сообщение того, кого хочешь назначить!")

    cmd = message.text.lower()
    if "дать" in cmd:
        if target_user.id not in bot_admins:
            bot_admins.append(target_user.id)
            bot.send_message(message.chat.id, f"ОДНОЗНАЧНО! {target_user.first_name} теперь в нашей команде! Наводи порядок, внучок!")
    else:
        if target_user.id in bot_admins:
            bot_admins.remove(target_user.id)
            bot.send_message(message.chat.id, f"ГНАТЬ ЕГО! {target_user.first_name} лишен всех полномочий! Вон из зала!")

# --- МОДЕРАЦИЯ (БАН, МУТ, КИК, ВАРН) ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().split()[0] in ["бан", "мут", "кик", "варн"])
def moderate(message):
    if message.chat.type == 'private': return
    if message.from_user.id not in bot_admins:
        return bot.reply_to(message, "Ты кто такой? У тебя нет мандата на такие действия! Подонок!")

    if not message.reply_to_message:
        return bot.reply_to(message, "Чтобы наказать негодяя, ответь этой командой на его сообщение!")

    target = message.reply_to_message.from_user
    cmd = message.text.lower().split()[0]
    reason = get_reason(message.text, cmd)

    try:
        if cmd == "бан":
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"ПОШЕЛ ВОН! {target.first_name} забанен. Причина: {reason}")
        
        elif cmd == "кик":
            bot.unban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"ВЫШВЫРНУЛИ! {target.first_name}, гуляй отсюда! Причина: {reason}")

        elif cmd == "мут":
            bot.restrict_chat_member(message.chat.id, target.id, until_date=time.time()+600)
            bot.send_message(message.chat.id, f"МОЛЧАТЬ! {target.first_name} в муте на 10 минут. Причина: {reason}")

        elif cmd == "варн":
            uid = target.id
            warns[uid] = warns.get(uid, 0) + 1
            if warns[uid] >= 3:
                bot.ban_chat_member(message.chat.id, uid)
                bot.send_message(message.chat.id, f"ВСЁ! ТРЕТИЙ ВАРН! {target.first_name} отправляется в ГУЛАГ!")
                warns[uid] = 0
            else:
                bot.send_message(message.chat.id, f"ПРЕДУПРЕЖДАЮ! {target.first_name}, у тебя {warns[uid]}/3 варнов. Причина: {reason}")

    except Exception as e:
        bot.reply_to(message, f"Не могу наказать! Видимо, этот подонок тоже админ! ({e})")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ ---

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("бот кто"))
def who_cool(message):
    if message.chat.type == 'private': 
        return bot.reply_to(message, "В этой коморке только мы с тобой. Выбирать не из кого!")
    
    text = message.text.lower()
    # Умный поиск цели после слов "кто крутой"
    subject = text.replace("бот кто крутой", "").strip()
    
    if not subject:
        user = message.from_user
        mention = f"@{user.username}" if user.username else user.first_name
    else:
        mention = subject.capitalize()

    responses = [
        f"Однозначно, {mention} — мощь! Остальные — подонки!",
        f"Я сказал — {mention}! Это наш человек!",
        f"Посмотрите на {mention}, вот на кого надо равняться!"
    ]
    bot.reply_to(message, random.choice(responses))

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.lower().startswith(("бот кто", "бан", "мут", "кик", "варн")): return
    try:
        res = model.generate_content(f"{SYSTEM_PROMPT}\n\nПишет внучок: {message.text}")
        bot.reply_to(message, res.text)
    except: pass

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        res = model.generate_content([f"{SYSTEM_PROMPT}\n\nЕдко прокомментируй это безобразие:", img])
        bot.reply_to(message, res.text)
    except: pass

app = Flask(__name__)
@app.route('/')
def h(): return "Бот-Дед под твоим управлением!"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    bot.infinity_polling()
