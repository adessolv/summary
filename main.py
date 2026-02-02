import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

from perplexity import AsyncPerplexity

load_dotenv()

TOKEN = os.getenv("TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# клиент, указываем base_url Perplexity [web:21][web:23]
px_client = AsyncOpenAI(
    api_key=PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai",
)

chat_history: dict[int, list[str]] = {}


@dp.message(F.text, ~Command("summary"))
async def collect_messages(message: types.Message):
    chat_id = message.chat.id
    chat_history.setdefault(chat_id, [])

    entry = f"{message.from_user.full_name}: {message.text}"
    chat_history[chat_id].append(entry)
    if len(chat_history[chat_id]) > 100:
        chat_history[chat_id].pop(0)


@dp.message(Command("summary"))
async def summarize_chat(message: types.Message):
    chat_id = message.chat.id
    history = chat_history.get(chat_id, [])

    if not history:
        await message.answer("Пока нет сообщений для суммаризации.")
        return

    text_to_analyze = "\n".join(history)

    prompt = (
        "Ты делаешь краткое саммари Telegram‑переписки: темы, решения, next steps. "
        "Максимум 10 пунктов.\n\n"
        f"Сообщения:\n{text_to_analyze}"
    )

    try:
        completion = await px_client.chat.completions.create(
            model="sonar-pro",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes group chats."},
                {"role": "user", "content": prompt},
            ],
        )
        summary = completion.choices[0].message.content
        await message.answer(f"<b>Саммари чата:</b>\n\n{summary}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка Perplexity API: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())