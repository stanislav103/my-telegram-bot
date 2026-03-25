from aiogram.fsm.state import State, StatesGroup

class WeatherForm(StatesGroup):
    waiting_for_city = State()