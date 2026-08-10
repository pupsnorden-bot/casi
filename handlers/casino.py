import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.db import db
from database.models import User
from states.casino import CasinoStates
from utils.casino_logic import check_win

router = Router()

GAME_BUTTONS = {
    "🎲": [
        "Четное",
        "Нечетное",
        "Больше 3",
        "Меньше 4",
        "Число 1",
        "Число 2",
        "Число 3",
        "Число 4",
        "Число 5",
        "Число 6",
    ],
    "🎯": ["Яблочко", "Мимо", "Красное", "Белое"],
    "🎰": ["Три семерки (777)", "Любые 3 в ряд", "2 подряд одинаковых"],
    "🏀": ["Попал", "Не попал", "Застрянет"],
    "⚽": ["Попал", "Не попал", "От штанги", "Девятка"],
    "🎳": ["Страйк", "Не попал", "Сбито 1 кегля", "Сбито 3 кегли", "Сбито 4 кегли", "Сбито 5 кеглей"],
}


def get_game_keyboard(user_id: int):
    keyboard = []
    for emoji in ["🎲", "🎯", "🎰", "🏀", "⚽", "🎳"]:
        keyboard.append([
            InlineKeyboardButton(text=emoji, callback_data=f"casino_game:{emoji}:{user_id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_outcome_keyboard(emoji: str, user_id: int):
    buttons = [
        InlineKeyboardButton(
            text=outcome,
            callback_data=f"casino_outcome:{emoji}:{outcome}:{user_id}",
        )
        for outcome in GAME_BUTTONS[emoji]
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)])


@router.message(Command("casino"))
async def casino_start(message: Message, state: FSMContext):
    await message.answer("Выбери игру для ставки:", reply_markup=get_game_keyboard(message.from_user.id))
    await state.set_state(CasinoStates.waiting_for_pick)


@router.callback_query(F.data.startswith("casino_game:"))
async def casino_pick(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    data = callback.data.split(":")
    if len(data) != 3:
        return

    _, emoji, creator_id_raw = data
    creator_id = int(creator_id_raw)

    if callback.from_user.id != creator_id:
        await callback.answer("Это не твоя игра! Вызови /casino", show_alert=True)
        return

    await callback.message.edit_text(
        f"Выбрана игра: {emoji}\nВыбери исход:",
        reply_markup=get_outcome_keyboard(emoji, creator_id),
    )
    await state.update_data(game=emoji, creator_id=creator_id)
    await state.set_state(CasinoStates.waiting_for_bet)
    await callback.answer()


@router.callback_query(F.data.startswith("casino_outcome:"))
async def casino_outcome(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    data = callback.data.split(":")
    if len(data) != 4:
        return

    _, emoji, outcome, creator_id_raw = data
    creator_id = int(creator_id_raw)

    if callback.from_user.id != creator_id:
        await callback.answer("Это не твоя игра! Вызови /casino", show_alert=True)
        return

    await state.update_data(game=emoji, outcome=outcome, creator_id=creator_id)
    await callback.message.delete()
    prompt = await callback.message.answer(f"{emoji} | {outcome}\nВведите сумму ставки:")
    await state.update_data(prompt_message_id=prompt.message_id)
    await callback.answer()


@router.message(CasinoStates.waiting_for_bet)
async def casino_waiting_for_bet(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_text = message.text or ""

    try:
        amount = int(user_text)
    except ValueError:
        err_msg = await message.answer("Сумма должна быть целым числом.")
        await asyncio.sleep(3)
        await err_msg.delete()
        await message.delete()
        return

    if amount <= 0:
        err_msg = await message.answer("Сумма должна быть больше 0.")
        await asyncio.sleep(3)
        await err_msg.delete()
        await message.delete()
        return

    async with db.session_factory() as session:
        user = await session.get(User, (user_id, chat_id))
        if user is None:
            user = User(user_id=user_id, chat_id=chat_id, balance=500, daily_words=0)
            session.add(user)

        if user.balance < amount:
            err_msg = await message.answer(f"Недостаточно монет! Ваш баланс: {user.balance}")
            await asyncio.sleep(3)
            await err_msg.delete()
            await message.delete()
            return

        user.balance -= amount
        await session.commit()

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    if prompt_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
            await message.delete()
        except Exception:
            pass

    emoji = data.get("game")
    outcome = data.get("outcome")

    if not emoji or not outcome:
        await message.answer("Сессия игры была сброшена. Попробуйте ещё раз через /casino.")
        await state.clear()
        return

    dice_message = await message.answer_dice(emoji=emoji)
    await asyncio.sleep(3.5)

    value = getattr(dice_message, "dice", None)
    dice_value = value.value if value is not None else 1
    is_win, multiplier = check_win(emoji, outcome, dice_value)
    payout = int(amount * multiplier) if is_win else 0

    if is_win:
        async with db.session_factory() as session:
            user = await session.get(User, (user_id, chat_id))
            if user is not None:
                user.balance += payout
                await session.commit()

    await message.answer(
        f"🎲 Результат: {emoji} | исход: {outcome}\n"
        f"Значение: {dice_value}\n"
        f"{'✅ Выигрыш! Платёж: ' + str(payout) if is_win else '❌ Проигрыш'}\n"
        f"Коэффициент: x{multiplier}",
    )
    await state.clear()
