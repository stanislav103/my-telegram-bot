from aiogram.fsm.state import State, StatesGroup


class WeatherForm(StatesGroup):
    waiting_for_city = State()


class EstimateStates(StatesGroup):
    # Базова інформація
    object_name      = State()   # Назва об'єкту
    system_type      = State()   # Пінопласт / Мінвата
    insulation_thick = State()   # Товщина утеплювача (мм)
    paint_type       = State()   # Тип фарби
    building_height  = State()   # Висота будівлі (м)
    perimeter        = State()   # Периметр будівлі (м)

    # Плоскості фасаду
    plane_count      = State()   # Кількість плоскостей
    plane_areas      = State()   # Площа кожної плоскості (по одній)

    # Кути
    corner_count     = State()   # Кількість зовнішніх кутів

    # Вікна
    window_count     = State()   # Кількість вікон
    window_sizes     = State()   # Розміри кожного вікна (по одному)

    # Двері
    door_count       = State()   # Кількість дверей
    door_sizes       = State()   # Розміри кожної двері (по одній)

    # Відкоси та доставка
    reveal_depth     = State()   # Глибина відкосів (м)
    delivery_cost    = State()   # Вартість доставки (грн)
    need_scaffold    = State()   # Потрібні ліси? Так/Ні

    # Підтвердження
    confirm          = State()   # Підтвердження і генерація кошторису


class HistoryStates(StatesGroup):
    filter_choice    = State()   # Вибір фільтру (дата / назва / всі)
    filter_date      = State()   # Введення дати
    filter_name      = State()   # Введення назви об'єкту
    select_estimate  = State()   # Вибір кошторису зі списку
