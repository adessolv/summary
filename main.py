import os
import asyncio
import logging
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from openai import AsyncOpenAI

load_dotenv()

TOKEN = os.getenv("TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Проверка ключей
if not TOKEN or not PERPLEXITY_API_KEY:
    exit("Ошибка: Добавь TELEGRAM_TOKEN и PERPLEXITY_API_KEY в .env файл")

# Инициализация бота (aiogram 3.x стиль) [web:34][web:40]
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Клиент Perplexity через OpenAI-совместимый интерфейс [web:21]
px_client = AsyncOpenAI(
    api_key=PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
)

# Хранилище (в памяти)
chat_history = {}


@dp.message(F.text, ~Command("summary"))
async def collect_messages(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    user_name = message.from_user.full_name or "Аноним"
    chat_history[chat_id].append(f"{user_name}: {message.text}")

    # Храним только последние 50 сообщений для экономии токенов
    if len(chat_history[chat_id]) > 50:
        chat_history[chat_id].pop(0)


@dp.message(Command("summary"))
async def summarize_chat(message: types.Message):
    chat_id = message.chat.id
    history = chat_history.get(chat_id, [])

    if not history:
        await message.answer("Слишком мало данных для анализа. Пообщайтесь еще немного!")
        return

    text_to_analyze = "\n".join(history)

    processing_msg = await message.answer("🔄 Генерирую выжимку...")

    try:
        # Используем модель sonar-pro (актуальна на февраль 2026) [web:21]
        response = await px_client.chat.completions.create(
            model="sonar-pro",
            messages=[
                {
                    "role": "system",
                    "content": "Ты профессиональный суммаризатор. Сделай краткую выжимку переписки на русском языке. Используй буллиты."
                },
                {
                    "role": "user",
                    "content": f"Проанализируй эти сообщения и выдели главное:\n\n{text_to_analyze}"
                }
            ]
        )

        summary = response.choices[0].message.content
        await processing_msg.edit_text(f"<b>📝 Итоги обсуждения:</b>\n\n{summary}")

    except Exception as e:
        logging.error(f"API Error: {e}")
        await processing_msg.edit_text(f"❌ Ошибка при связи с ИИ. Проверь API-ключ.")


async def main():
    # Запуск логирования [web:34]
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")