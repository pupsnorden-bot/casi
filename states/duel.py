from aiogram.fsm.state import State, StatesGroup


class DuelStates(StatesGroup):
    waiting_for_bet = State()
    waiting_for_opponent_outcome = State()
