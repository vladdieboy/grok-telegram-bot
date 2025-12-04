import os
import telebot
import requests
import base64
import time

# Токены берём из переменных окружения Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")

if not TELEGRAM_TOKEN or not GROK_API_KEY:
    print("ОШИБКА: Добавьте токены в Variables!")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

CHAT_URL = "https://api.x.ai/v1/chat/completions"
IMAGE_URL = "https://api.x.ai/v1/images/generations"

history = {}

@bot.message_handler(func=lambda m: True)
def handle(message):
    user_id = message.from_user.id
    text = (message.text or message.caption or "").strip()

    if user_id not in history:
        history[user_id] = [{"role": "system", "content": "Ты — Grok 4.1 от xAI. Отвечай на русском языке."}]

    # Генерация картинки
    if text.lower().startswith(("сгенерируй фото", "нарисуй", "image:", "фото:")):
        prompt = text
        for prefix in ["сгенерируй фото", "нарисуй", "image:", "фото:"]:
            prompt = prompt.lower().replace(prefix, "", 1).strip()
        bot.reply_to(message, "Генерирую картинку через Aurora…")
        try:
            r = requests.post(
                IMAGE_URL,
                headers={"Authorization": f"Bearer {GROK_API_KEY}"},
                json={"model": "grok-2-image-1212", "prompt": prompt, "n": 1},
                timeout=90
            )
            if r.status_code == 200:
                img_url = r.json()["data"][0]["url"]
                img = requests.get(img_url, timeout=30).content
                bot.send_photo(message.chat.id, img, caption=f"Промпт: {prompt}")
            else:
                bot.reply_to(message, f"Ошибка API: {r.status_code}\n{r.text}")
        except Exception as e:
            bot.reply_to(message, f"Ошибка генерации: {e}")
        return

    # Анализ фото
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        photo = bot.download_file(file_info.file_path)
        b64 = base64.b64encode(photo).decode()
        history[user_id].append({
            "role": "user",
            "content": [
                {"type": "text", "text": text or "Опиши это фото подробно"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        })
    else:
        history[user_id].append({"role": "user", "content": text})

    # Обычный чат
    try:
        payload = {
            "messages": history[user_id],
            "model": "grok-4-1-fast-reasoning",
            "temperature": 0.8,
            "max_tokens": 4000
        }
        r = requests.post(
            CHAT_URL,
            headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=90
        )
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"]
        history[user_id].append({"role": "assistant", "content": answer})

        for i in range(0, len(answer), 4000):
            bot.reply_to(message, answer[i:i+4000])
            time.sleep(0.4)

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

if __name__ == "__main__":
    print("Grok 4.1 бот запущен на Railway!")
    bot.infinity_polling(none_stop=True, interval=0, timeout=90)
