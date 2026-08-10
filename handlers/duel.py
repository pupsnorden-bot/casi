import asyncio
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.db import db
from database.models import Duel, User
from states.duel import DuelStates
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
    "🏀": ["Попал", "Не попал", "Застрянет"],
    "⚽": ["Попал", "Не попал", "От штанги", "Девятка"],
    "🎳": ["Страйк", "Не попал", "Сбито 1 кегля", "Сбито 3 кегли", "Сбито 4 кегли", "Сбито 5 кеглей"],
}


def _username(user_id: int, username: Optional[str]) -> str:
    return f"@{username}" if username else f"@user{user_id}"


def get_game_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=emoji, callback_data=f"duel_game:{emoji}")]
        for emoji in ["🎲", "🎯", "🏀", "⚽", "🎳"]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_outcome_keyboard(game_type: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=outcome, callback_data=f"duel_creator_outcome:{game_type}:{outcome}")
        for outcome in GAME_BUTTONS.get(game_type, [])
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)])


def get_opponent_outcome_keyboard(game_type: str, duel_id: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=outcome, callback_data=f"duel_opponent_outcome:{duel_id}:{outcome}")
        for outcome in GAME_BUTTONS.get(game_type, [])
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)])


@router.message(Command("duel"))
async def duel_start(message: Message):
    if message.from_user is None:
        return

    await message.answer("Выбери игру для дуэли:", reply_markup=get_game_keyboard())


@router.callback_query(F.data.startswith("duel_game:"))
async def duel_select_game(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    _, emoji = callback.data.split(":", 1)
    await callback.message.edit_text(
        f"Выбрана игра: {emoji}\nВыбери свой исход:",
        reply_markup=get_outcome_keyboard(emoji),
    )
    await state.update_data(game_type=emoji, creator_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("duel_creator_outcome:"))
async def duel_select_creator_outcome(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    data = callback.data.split(":")
    if len(data) != 3:
        return

    _, game_type, outcome = data
    if callback.from_user.id != int((await state.get_data()).get("creator_id", callback.from_user.id)):
        await callback.answer("Это не твоя дуэль! Используй /duel", show_alert=True)
        return

    await state.update_data(game_type=game_type, creator_outcome=outcome)
    prompt = await callback.message.answer(f"{game_type} | {outcome}\nВведите сумму ставки:")
    await state.update_data(prompt_message_id=prompt.message_id)
    await state.set_state(DuelStates.waiting_for_bet)
    await callback.answer()


@router.message(DuelStates.waiting_for_bet)
async def duel_waiting_for_bet(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    user_text = (message.text or "").strip()
    data = await state.get_data()
    creator_id = data.get("creator_id")
    game_type = data.get("game_type")
    creator_outcome = data.get("creator_outcome")

    if message.from_user.id != creator_id:
        await message.answer("Это не твоя дуэль.")
        await state.clear()
        return

    try:
        bet = int(user_text)
    except ValueError:
        err = await message.answer("Сумма ставки должна быть целым числом.")
        await asyncio.sleep(3)
        await err.delete()
        await message.delete()
        return

    if bet <= 0:
        err = await message.answer("Сумма ставки должна быть больше 0.")
        await asyncio.sleep(3)
        await err.delete()
        await message.delete()
        return

    async with db.session_factory() as session:
        creator = await session.get(User, (message.from_user.id, message.chat.id))
        if creator is None:
            creator = User(user_id=message.from_user.id, chat_id=message.chat.id, balance=500, daily_words=0)
            session.add(creator)

        if creator.balance < bet:
            err = await message.answer(f"Недостаточно монет для дуэли. Ваш баланс: {creator.balance}")
            await asyncio.sleep(3)
            await err.delete()
            await message.delete()
            return

        creator.balance -= bet
        duel = Duel(
            chat_id=message.chat.id,
            creator_id=message.from_user.id,
            creator_username=message.from_user.username,
            creator_outcome=creator_outcome,
            bet=bet,
            game_type=game_type,
            status="WAITING",
        )
        session.add(duel)
        await session.commit()
        await session.refresh(duel)

    prompt_message_id = data.get("prompt_message_id")
    if prompt_message_id is not None:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
        except Exception:
            pass

    creator_tag = _username(message.from_user.id, message.from_user.username)
    accept_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⚔️ Принять вызов", callback_data=f"duel_accept:{duel.id}")]]
    )

    await message.answer(
        f"⚔️ <b>ДУЭЛЬ СОЗДАНА!</b>\n\n"
        f"<b>Создатель:</b> {creator_tag}\n"
        f"<b>Игра:</b> {game_type} | <b>Исход:</b> {creator_outcome}\n\n"
        f"<b>Ставка:</b> {bet} монет",
        reply_markup=accept_keyboard,
    )
    await message.delete()
    await state.clear()


@router.callback_query(F.data.startswith("duel_accept:"))
async def duel_accept(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    duel_id = int(callback.data.split(":", 1)[1])

    async with db.session_factory() as session:
        duel = await session.get(Duel, duel_id)
        if duel is None:
            await callback.answer("Дуэль не найдена.", show_alert=True)
            return

        if duel.status != "WAITING":
            await callback.answer("Эта дуэль уже закрыта.", show_alert=True)
            return

        if callback.from_user.id == duel.creator_id:
            await callback.answer("Нельзя принять свой собственный вызов.", show_alert=True)
            return

        opponent = await session.get(User, (callback.from_user.id, callback.message.chat.id))
        if opponent is None:
            opponent = User(user_id=callback.from_user.id, chat_id=callback.message.chat.id, balance=500, daily_words=0)
            session.add(opponent)

        if opponent.balance < duel.bet:
            await callback.answer("Недостаточно монет для принятия дуэли.", show_alert=True)
            return

    await callback.message.edit_text(
        f"Выбери свой исход для дуэли #{duel_id}:\n{duel.game_type}",
        reply_markup=get_opponent_outcome_keyboard(duel.game_type, duel_id),
    )
    await state.set_state(DuelStates.waiting_for_opponent_outcome)
    await state.update_data(duel_id=duel_id, opponent_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("duel_opponent_outcome:"))
async def duel_opponent_outcome(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    data = callback.data.split(":")
    if len(data) != 3:
        return

    _, duel_id_raw, opponent_outcome = data
    duel_id = int(duel_id_raw)
    duel_data = await state.get_data()

    if duel_data.get("duel_id") != duel_id or duel_data.get("opponent_id") != callback.from_user.id:
        await callback.answer("Сессия дуэли неактивна.", show_alert=True)
        return

    async with db.session_factory() as session:
        duel = await session.get(Duel, duel_id)
        if duel is None:
            await callback.answer("Дуэль больше не существует.", show_alert=True)
            return

        if duel.status != "WAITING":
            await callback.answer("Эта дуэль уже началась или завершилась.", show_alert=True)
            return

        if callback.from_user.id == duel.creator_id:
            await callback.answer("Нельзя выбирать исход от имени создателя.", show_alert=True)
            return

        opponent = await session.get(User, (callback.from_user.id, callback.message.chat.id))
        if opponent is None:
            opponent = User(user_id=callback.from_user.id, chat_id=callback.message.chat.id, balance=500, daily_words=0)
            session.add(opponent)

        if opponent.balance < duel.bet:
            await callback.answer("Недостаточно монет.", show_alert=True)
            return

        opponent.balance -= duel.bet
        duel.opponent_id = callback.from_user.id
        duel.opponent_username = callback.from_user.username
        duel.opponent_outcome = opponent_outcome
        duel.status = "ACTIVE"
        await session.commit()

    dice_message = await callback.message.answer_dice(emoji=duel.game_type)
    await asyncio.sleep(3.5)

    dice_value = getattr(dice_message.dice, "value", 1)
    creator_win, _ = check_win(duel.game_type, duel.creator_outcome, dice_value)
    opponent_win, _ = check_win(duel.game_type, duel.opponent_outcome, dice_value)

    async with db.session_factory() as session:
        creator = await session.get(User, (duel.creator_id, duel.chat_id))
        opponent = await session.get(User, (duel.opponent_id, duel.chat_id))

        if creator is None:
            creator = User(user_id=duel.creator_id, chat_id=duel.chat_id, balance=500, daily_words=0)
            session.add(creator)
        if opponent is None:
            opponent = User(user_id=duel.opponent_id, chat_id=duel.chat_id, balance=500, daily_words=0)
            session.add(opponent)

        if duel.creator_outcome == duel.opponent_outcome:
            if creator_win and opponent_win:
                creator.balance += int(duel.bet * 1.0)
                opponent.balance += int(duel.bet * 1.0)
            elif not creator_win and not opponent_win:
                creator.balance += int(duel.bet * 0.5)
                opponent.balance += int(duel.bet * 0.5)
        else:
            if creator_win and not opponent_win:
                creator.balance += duel.bet * 2
            elif opponent_win and not creator_win:
                opponent.balance += duel.bet * 2

        duel.status = "FINISHED"
        await session.commit()

    creator_tag = _username(duel.creator_id, duel.creator_username)
    opponent_tag = _username(duel.opponent_id or 0, duel.opponent_username)

    final_text = (
        f"⚔️ <b>ИТОГ ДУЭЛИ</b>\n\n"
        f"<b>Создатель:</b> {creator_tag} ({duel.creator_outcome})\n"
        f"<b>Противник:</b> {opponent_tag} ({duel.opponent_outcome})\n"
        f"<b>Игра:</b> {duel.game_type}\n"
        f"<b>Кость:</b> {dice_value}\n\n"
        f"<b>Результат:</b> "
    )

    if duel.creator_outcome == duel.opponent_outcome:
        if creator_win and opponent_win:
            final_text += "Оба выиграли — банк делится 50/50."
        else:
            final_text += "Оба проиграли — каждому возвращается 50% ставки."
    else:
        if creator_win and not opponent_win:
            final_text += f"Победил {creator_tag}!"
        elif opponent_win and not creator_win:
            final_text += f"Победил {opponent_tag}!"
        else:
            final_text += "Никто не выиграл — банк сгорел."

    await callback.message.answer(final_text)
    await state.clear()
    await callback.answer()
