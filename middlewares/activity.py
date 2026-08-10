from typing import Any

from aiogram import BaseMiddleware, types

from database.db import db
from database.models import User


class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict[str, Any]):
        if not isinstance(event, types.Message):
            return await handler(event, data)

        chat = event.chat
        if chat.type not in ("group", "supergroup"):
            return await handler(event, data)

        if event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        chat_id = chat.id

        async with db.session_factory() as session:
            user = await session.get(User, (user_id, chat_id))

            if user is None:
                user = User(user_id=user_id, chat_id=chat_id, balance=500, daily_words=0)
                session.add(user)

            text = event.text or event.caption or ""
            words = len(text.split()) if text.strip() else 1
            user.daily_words += words

            await session.commit()

        return await handler(event, data)
