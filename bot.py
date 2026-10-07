import asyncio
from aiogram import Bot, Dispatcher

from config import TOKEN
from database import init_db, get_recent_words
from handlers.examples import prefetch_examples
from handlers import register_handlers

bot = Bot(token=TOKEN)
dp = Dispatcher()


async def main():
    await init_db()
    register_handlers(dp)

    # 👇 прогреваем кэш для последних 50 слов в фоне
    words = await get_recent_words(50)
    asyncio.create_task(prefetch_examples(words))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())