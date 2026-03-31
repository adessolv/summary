import asyncio
import os
import json
from collections import Counter

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties

from cerebras.cloud.sdk import AsyncCerebras  # Cerebras SDK

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден в .env")
if not CEREBRAS_API_KEY:
    raise RuntimeError("CEREBRAS_API_KEY не найден в .env")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Клиент Cerebras (асинхронный)
cerebras_client = AsyncCerebras(api_key=CEREBRAS_API_KEY)

async def summarize_with_cerebras(text: str) -> str:
    max_chars = 20000
    if len(text) > max_chars:
        text = text[-max_chars:]

    prompt = """Сделай КРАТКОЕ саммари Telegram-чата за день.

<b>ТВЁРДЫЙ ФОРМАТ ответа:</b>

📋 <b>Основные темы:</b>
1. <b>🧴 Пот и дезодоранты</b> — обсуждали способы борьбы с потливостью
2. <b>📱 Краши приложений</b> — делились скринами багов  
3. <b>🐦 Птичьи экскурсии</b> — планировали поход за птицами
...

ПРАВИЛА:
• <b>ЖИРНЫЙ ШРИФТ &lt;b&gt;</b> для ВСЕХ тем (название + номер)
• Каждая тема: emoji + название + 1-2 предложения
• Максимум 5 тем
• НЕТ **
• Русский язык

Переписка:
{text}"""

    completion = await cerebras_client.chat.completions.create(
        model="llama3.1-8b",
        messages=[
            {"role": "system", "content": "СТРОГО копируй HTML-формат из примера. <b>Жирный</b> для номеров и названий тем. Только <b>, никаких **."},
            {"role": "user", "content": prompt.format(text=text)},
        ],
        max_tokens=500,
        temperature=0.1,  # Максимально строго
    )

    return completion.choices[0].message.content

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        "🚀 Привет! Пришли JSON-файл экспорта чата за день.\n\n"
        "Я сделаю:\n"
        "• Саммари дня с темами и выводами (Cerebras Llama 3.1)\n"
        "• Топ-3 самых активных авторов\n\n"
        "Формат как у Telegram-экспорта: поле messages[]."
    )

@dp.message(F.content_type == ContentType.DOCUMENT)
async def handle_json(message: types.Message):
    print(f"🔍 Файл от {message.from_user.full_name}")

    doc = message.document
    print(f"📄 {doc.file_name}")

    if not doc.file_name.lower().endswith(".json"):
        await message.answer("❌ Нужен JSON-файл экспорта чата 🙏")
        return

    try:
        print("📥 Скачиваю файл...")
        file = await bot.get_file(doc.file_id)
        downloaded = await bot.download_file(file.file_path)
        print("✅ Файл скачан")
    except Exception as e:
        print(f"❌ Ошибка скачивания: {e}")
        await message.answer("❌ Не удалось скачать файл.")
        return

    try:
        print("📖 Парсю JSON...")
        data = json.loads(downloaded.read().decode("utf-8"))
        print(f"✅ JSON прочитан, ключей: {len(data)}")
    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        await message.answer(f"❌ Ошибка чтения JSON: {e}")
        return

    messages = data.get("messages", [])
    print(f"📨 Найдено {len(messages)} сообщений")

    if not messages:
        await message.answer("❌ В JSON нет поля messages или оно пустое.")
        return

    # Извлекаем текст и авторов
    lines = []
    authors = []

    print("🔍 Обрабатываю сообщения...")

    for m in messages:
        if m.get("type") != "message":
            continue

        text = m.get("text")
        if isinstance(text, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )
        if not text or len(text.strip()) < 2:
            continue

        author = m.get("from") or "Unknown"
        authors.append(author)
        lines.append(f"{author}: {text}")

        # Ограничим до первых 300 сообщений, чтобы не уходить в огромный промпт
        if len(lines) >= 300:
            break

    print(f"✅ Взято {len(lines)} текстовых сообщений, авторов: {len(set(authors))}")

    if not lines:
        await message.answer("❌ Не нашёл текстовых сообщений в JSON.")
        return

    # Топ-3 авторов
    counter = Counter(authors)
    top3 = counter.most_common(3)
    top_lines = [
        f"{i+1}. {name} — {count} сообщений"
        for i, (name, count) in enumerate(top3)
    ]

    await message.answer("⚙️ Считаю саммари через Cerebras, подожди немного...")

    joined = "\n".join(lines)

    try:
        summary = await summarize_with_cerebras(joined)
    except Exception as e:
        print(f"❌ Ошибка Cerebras: {e}")
        await message.answer(f"❌ Ошибка при обращении к Cerebras: {e}")
        return

    text_resp = (
        "<b>📝 Саммари дня:</b>\n\n"
        f"{summary}\n\n"
        "<b>🏆 Топ-3 самых активных авторов:</b>\n"
        + "\n".join(top_lines)
    )

    await message.answer(text_resp)
    print("✅ Отчёт отправлен пользователю")

async def main():
    print("🤖 Бот запущен!")
    # важно: правильно закрыть клиент Cerebras при завершении
    try:
        await dp.start_polling(bot)
    finally:
        await cerebras_client.close()

if __name__ == "__main__":
    asyncio.run(main())
