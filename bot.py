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

# === ТВОИ КАРТИНКИ ===
PETER_IMAGES = [
    "https://i.postimg.cc/zV0Lqc8k/image.jpg" 
]

IMAGE_CHANCE = 10 

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

def is_admin(chat_id, user_id):
    if user_id == OWNER_ID: return True
    if chat_id > 0: return True 
    try:
        admins = bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.user.id == user_id:
                return True
    except: pass
    return False

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"хехехе, питер гриффин на связи. ключей: {len(API_KEYS)}.")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        if new_user.id == bot.get_me().id:
            bot.send_message(message.chat.id, "о, здорово. я теперь тут главный. несите пиво.")
        else:
            bot.reply_to(message, f"о, еще один лузер приперся. здорово, {new_user.first_name.lower()}. читай правила и не беси меня, а то выкину.")

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
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
        if message.content_type == 'text':
            text_lower = message.text.lower()
            parts = text_lower.split()
            cmd = parts[0] if parts else ""

            # ПРАВИЛА
            if cmd in ["правила", "/rules"]:
                rules_text = (
                    "мои правила простые:\n"
                    "1. я тут главный, а мой создатель — бог.\n"
                    "2. не спамить и не ныть, а то забаню к чертям.\n"
                    "3. каждый обязан скинуться мне на пиво «потакет».\n"
                    "всё понял? свободен."
                )
                bot.reply_to(message, rules_text)
                return

            # МОДЕРАЦИЯ
            if message.reply_to_message and cmd in ["бан", "мут", "кик", "разбан", "анмут", "анбан"]:
                if not is_admin(message.chat.id, message.from_user.id):
                    bot.reply_to(message, "заткнись, у тебя нет прав мне указывать. иди лоис поуказывай.")
                    return
                
                target_user_id = message.reply_to_message.from_user.id
                target_name = message.reply_to_message.from_user.first_name.lower()

                try:
                    if cmd == "бан":
                        bot.ban_chat_member(message.chat.id, target_user_id)
                        bot.reply_to(message, f"хехехе, выкинул этого лузера ({target_name}) на мороз. больше он тут не появится.")
                    
                    elif cmd == "кик":
                        bot.ban_chat_member(message.chat.id, target_user_id)
                        bot.unban_chat_member(message.chat.id, target_user_id)
                        bot.reply_to(message, f"пнул под зад {target_name}. пусть заходит заново, если поумнеет.")
                    
                    elif cmd == "мут":
                        # --- УМНЫЙ МУТ С РАСЧЕТОМ ВРЕМЕНИ ---
                        duration_seconds = 3600 # 1 час по умолчанию
                        time_text = "на час"

                        if len(parts) >= 2 and parts[1].isdigit():
                            amount = int(parts[1])
                            unit = parts[2] if len(parts) > 2 else "мин"

                            if any(unit.startswith(x) for x in ["мин", "м"]):
                                duration_seconds = amount * 60
                                time_text = f"на {amount} минут"
                            elif any(unit.startswith(x) for x in ["час", "ч"]):
                                duration_seconds = amount * 3600
                                time_text = f"на {amount} часов"
                            elif any(unit.startswith(x) for x in ["дн", "ден", "сут", "д"]):
                                duration_seconds = amount * 86400
                                time_text = f"на {amount} дней"
                            else:
                                duration_seconds = amount * 60
                                time_text = f"на {amount} минут"

                        bot.restrict_chat_member(message.chat.id, target_user_id, until_date=int(time.time() + duration_seconds))
                        bot.reply_to(message, f"заклеил рот скотчем ({target_name}) {time_text}. пусть посидит в тишине, а то разнылся тут.")
                    
                    elif cmd in ["разбан", "анбан"]:
                        bot.unban_chat_member(message.chat.id, target_user_id, only_if_banned=True)
                        bot.reply_to(message, f"ладно, пусть возвращается. я сегодня добрый.")
                    
                    elif cmd == "анмут":
                        bot.restrict_chat_member(message.chat.id, target_user_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
                        bot.reply_to(message, f"оторвал скотч с лица ({target_name}). говори, но не беси меня.")
                except Exception as e:
                    bot.reply_to(message, "че-то не вышло. эй, ты забыл дать мне админку в чате! я тебе что, маг?")
                return

            if text_lower == "картинка":
                if PETER_IMAGES: bot.send_photo(message.chat.id, PETER_IMAGES[0])
                return

            # ОТВЕТ НЕЙРОСЕТИ
            ans = ask_gemini(f"{p}\n\nсообщение: {message.text}")
            final_text = ans.lower() if ans else "пустой ответ"
            bot.reply_to(message, final_text)

            # РАНДОМНАЯ КАРТИНКА БЕЗ ПОДПИСИ
            if message.chat.type != "private" and len(PETER_IMAGES) > 0:
                if random.randint(1, 100) <= IMAGE_CHANCE:
                    bot.send_photo(message.chat.id, random.choice(PETER_IMAGES)) 

        # ОБРАБОТКА ФОТО ДЛЯ ID
        elif message.content_type == 'photo':
            file_id = message.photo[-1].file_id 
            
            if message.from_user.id == OWNER_ID:
                bot.reply_to(message, f"Код этой картинки для списка (скопируй):\n`{file_id}`", parse_mode="Markdown")

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
