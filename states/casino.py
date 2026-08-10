from aiogram.fsm.state import State, StatesGroup


class CasinoStates(StatesGroup):
    waiting_for_bet = State()
    waiting_for_pick = State()
