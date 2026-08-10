import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database.db import db
from handlers.casino import router as casino_router
from handlers.duel import router as duel_router
from handlers.economy import router as economy_router
from middlewares.activity import ActivityMiddleware
from services.scheduler import setup_scheduler


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    await db.init_db()

    dp.message.middleware(ActivityMiddleware())
    dp.include_router(economy_router)
    dp.include_router(casino_router)
    dp.include_router(duel_router)

    scheduler = setup_scheduler()
    scheduler.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
