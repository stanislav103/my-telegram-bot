from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import httpx

from config import WEATHER_API_KEY
from states import WeatherForm
from database import add_weather_request, get_user_history, get_user_stats

router = Router()


def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


@router.callback_query(F.data == "weather")
async def callback_weather(call: CallbackQuery, state: FSMContext):
    await state.set_state(WeatherForm.waiting_for_city)
    await call.message.answer("🌍 Введи название города:")
    await call.answer()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("❌ Отменено.")

@router.message(WeatherForm.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()
    await state.clear()

    async with httpx.AsyncClient() as client:
        params = {
            "q": city,
            "appid": WEATHER_API_KEY,
            "units": "metric",
            "lang": "ru"
        }
        response = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params
        )
        data = response.json()

    if data.get("cod") != 200:
        error_msg = data.get("message", "Неизвестная ошибка")
        await message.answer(
            f"❌ Ошибка: {error_msg}\n"
            f"Код ошибки: {data.get('cod')}\n"
            f"Город: {city}"
        )
        return

    await add_weather_request(message.from_user.id, city)

    temp = data["main"]["temp"]
    feels = data["main"]["feels_like"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    await message.answer(
        f"🌤 Погода в {city}:\n"
        f"🌡 Температура: {temp:.0f}°C\n"
        f"🤔 Ощущается как: {feels:.0f}°C\n"
        f"☁️ {desc.capitalize()}\n"
        f"💧 Влажность: {humidity}%\n"
        f"💨 Ветер: {wind} м/с",
        reply_markup=back_keyboard()
    )

@router.message(Command("history"))
async def cmd_history(message: Message):
    rows = await get_user_history(message.from_user.id)
    if not rows:
        await message.answer("Ты ещё не запрашивал погоду.", reply_markup=back_keyboard())
        return
    lines = [f"{i+1}. {city} — {at[:10]}" for i, (city, at) in enumerate(rows)]
    await message.answer(
        "🕒 Последние запросы:\n" + "\n".join(lines),
        reply_markup=back_keyboard()
    )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    count = await get_user_stats(message.from_user.id)
    await message.answer(
        f"📊 Ты запросил погоду {count} раз(а).",
        reply_markup=back_keyboard()
    )