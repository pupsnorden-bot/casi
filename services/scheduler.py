from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from database.db import db
from database.models import User


async def award_daily_activity() -> None:
    tz = ZoneInfo("Europe/Moscow")
    now = datetime.now(tz)
    mult = 2 if now.weekday() in (5, 6) else 1

    async with db.session_factory() as session:
        users = (await session.execute(
            select(User).where(User.daily_words > 0)
        )).scalars().all()

        for user in users:
            user.balance += user.daily_words * mult
            user.daily_words = 0

        await session.commit()


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        award_daily_activity,
        trigger=CronTrigger(hour=0, minute=0, second=0, timezone="Europe/Moscow"),
    )
    return scheduler
