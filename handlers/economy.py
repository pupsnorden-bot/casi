from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.db import db
from database.models import User

router = Router()


@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "Привет! Я игровой бот.\n\n"
        "Доступные команды:\n"
        "/casino — азартная игра\n"
        "/duel — дуэль с другим пользователем\n"
        "/give 100 — перевести монеты в ответе на сообщение\n\n"
        "Команды работают и в личных сообщениях, и в группах."
    )


def _parse_amount(value: str) -> Optional[int]:
    if value is None or not value.isdigit():
        return None
    amount = int(value)
    return amount if amount > 0 else None


@router.message(Command("give"))
async def give_command(message: Message):
    if message.from_user is None:
        return

    text = message.text or ""
    args = text.split()[1:]
    sender_id = message.from_user.id
    chat_id = message.chat.id

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Для перевода используйте ответ на сообщение пользователя и укажите сумму: /give 100")
        return

    recipient_id = message.reply_to_message.from_user.id
    amount = _parse_amount(args[0]) if len(args) == 1 else None

    if recipient_id == sender_id:
        await message.answer("Вы не можете переводить монеты самому себе.")
        return

    if amount is None:
        await message.answer("Сумма должна быть целым положительным числом больше 0.")
        return

    async with db.session_factory() as session:
        sender = await session.get(User, (sender_id, chat_id))
        recipient = await session.get(User, (recipient_id, chat_id))

        if sender is None:
            sender = User(user_id=sender_id, chat_id=chat_id, balance=500, daily_words=0)
            session.add(sender)
        if recipient is None:
            recipient = User(user_id=recipient_id, chat_id=chat_id, balance=500, daily_words=0)
            session.add(recipient)

        if sender.balance < amount:
            await message.answer("У вас недостаточно монет для перевода.")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Принять перевод",
                        callback_data=f"give_accept:{sender_id}:{recipient_id}:{amount}",
                    )
                ]
            ]
        )

        recipient_username = (
            f"@{message.reply_to_message.from_user.username}"
            if message.reply_to_message.from_user.username
            else f"@user{recipient_id}"
        )
        sender_username = f"@{message.from_user.username}" if message.from_user.username else f"@user{sender_id}"

        await message.answer(
            f"Пользователь {sender_username} переводит {amount} монет для {recipient_username}. Нажмите кнопку ниже для подтверждения.",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("give_accept:"))
async def give_accept(callback: CallbackQuery):
    if callback.message is None:
        return

    data = callback.data.split(":")
    if len(data) != 4:
        return

    _, sender_id_raw, recipient_id_raw, amount_raw = data
    sender_id = int(sender_id_raw)
    recipient_id = int(recipient_id_raw)
    amount = int(amount_raw)

    if callback.from_user.id != recipient_id:
        await callback.answer("Это перевод не для тебя!", show_alert=True)
        return

    chat_id = callback.message.chat.id

    async with db.session_factory() as session:
        sender = await session.get(User, (sender_id, chat_id))
        recipient = await session.get(User, (recipient_id, chat_id))

        if sender is None or recipient is None:
            await callback.answer("Не удалось выполнить перевод: участники не найдены.", show_alert=True)
            return

        if sender.balance < amount:
            await callback.answer("У отправителя недостаточно монет.", show_alert=True)
            return

        sender.balance -= amount
        recipient.balance += amount
        await session.commit()

    recipient_username = f"@{callback.from_user.username}" if callback.from_user.username else f"@user{recipient_id}"
    await callback.message.edit_text(
        f"✅ Перевод успешно выполнен! {recipient_username} получил {amount} монет.",
        reply_markup=None,
    )
    await callback.answer()
