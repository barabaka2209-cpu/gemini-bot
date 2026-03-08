import telebot
import os
import random
import time
import threading
from flask import Flask, request
from groq import Groq

# Конфиг из переменных окружения
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
OWNER_ID = 8067227894 

bot = telebot.TeleBot(TOKEN)
client = Groq(api_key=GROQ_KEY)
app = Flask(__name__)

PETER_IMAGES = ["https://i.postimg.cc/zV0Lqc8k/image.jpg"]
IMAGE_CHANCE = 10 

def ask_ai(prompt_text, system_prompt):
    """Запрос к Llama 3 через Groq (официально и быстро)"""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.8,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "мои мозги сейчас в отключке. это даже хуже, чем тот раз, когда я пытался переспорить гигантского цыпленка."

def is_admin(chat_id, user_id):
    if user_id == OWNER_ID or chat_id > 0: return True
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in admins)
    except: return False

def process_logic(message):
    """Основная логика в отдельном потоке"""
    try:
        # Настройка промпта
        if message.chat.type == "private":
            p = "ты вежливый ии-помощник. отвечай кратко и строго строчными буквами."
        elif message.from_user.id == OWNER_ID:
            p = "ты преданный слуга своего господина. называй его господином, будь почтителен. пиши строго строчными буквами."
        else:
            p = ("ты питер гриффин. ты ворчливый, ленивый и глуповатый. "
                 "постоянно шути, используй 'это даже хуже, чем тот раз, когда я...'. "
                 "отвечай едко и СТРОГО строчными буквами.")

        text_lower = message.text.lower()
        parts = text_lower.split()
        cmd = parts[0] if parts else ""

        # Команда Правила
        if cmd in ["правила", "/rules"]:
            bot.reply_to(message, "мои правила: я босс, ты нет. не спамить. не ныть. всё.")
            return

        # Модерация (бан, мут, кик)
        if message.reply_to_message and cmd in ["бан", "мут", "кик", "разбан", "анмут"]:
            if not is_admin(message.chat.id, message.from_user.id):
                bot.reply_to(message, "заткнись, лузер. у тебя нет прав.")
                return
            
            target_id = message.reply_to_message.from_user.id
            try:
                if cmd == "бан": bot.ban_chat_member(message.chat.id, target_id)
                elif cmd == "кик": 
                    bot.ban_chat_member(message.chat.id, target_id)
                    bot.unban_chat_member(message.chat.id, target_id)
                elif cmd == "мут": bot.restrict_chat_member(message.chat.id, target_id, until_date=int(time.time() + 3600))
                elif cmd == "анмут": bot.restrict_chat_member(message.chat.id, target_id, can_send_messages=True)
                
                bot.reply_to(message, f"хехехе, {cmd} выполнен успешно. я великолепен.")
            except:
                bot.reply_to(message, "дай мне админку сначала, гений.")
            return

        # Ответ ИИ
        bot.send_chat_action(message.chat.id, 'typing')
        ans = ask_ai(message.text, p)
        bot.reply_to(message, ans.lower() if ans else "пусто")

        # Рандомная картинка
        if message.chat.type != "private" and random.randint(1, 100) <= IMAGE_CHANCE:
            bot.send_photo(message.chat.id, random.choice(PETER_IMAGES))

    except Exception as e:
        print(f"Ошибка обработки: {e}")

@bot.message_handler(content_types=['text'])
def handle_all(message):
    threading.Thread(target=process_logic, args=(message,)).start()

@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "ok", 200

@app.route('/')
def webhook(): return "Питер Гриффин онлайн!", 200

if __name__ == "__main__":
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{host}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
