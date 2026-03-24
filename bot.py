import asyncio
import os
import httpx
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌤 Погода", callback_data="weather")],
        [InlineKeyboardButton(text="💰 Курс валют", callback_data="currency")],
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыбери раздел:",
        reply_markup=keyboard
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Я эхо-бот. Напиши что-нибудь!")

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌤 Погода", callback_data="weather")],
        [InlineKeyboardButton(text="💰 Курс валют", callback_data="currency")],
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ])
    await message.answer("Выбери раздел:", reply_markup=keyboard)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

@dp.callback_query()
async def handle_callback(callback):
    if callback.data == "weather":
        await callback.answer()
        city = "Odessa"
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
        if data.get("cod") != 200:
            await callback.message.answer("⚠️ Не удалось получить погоду, попробуй позже")
            return

        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        desc = data["weather"][0]["description"]
        
        await callback.message.answer(
            f"🌤 Погода в {city}:\n"
            f"🌡 Температура: {temp}°C\n"
            f"🤔 Ощущается как: {feels}°C\n"
            f"☁️ {desc.capitalize()}"
        )
    elif callback.data == "currency":
        await callback.answer()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏦 Офіційний (НБУ)", callback_data="currency_nbu")],
            [InlineKeyboardButton(text="💱 Ринковий (Mono)", callback_data="currency_market")],
        ])
        await callback.message.answer("Який курс показати?", reply_markup=keyboard)

    elif callback.data == "currency_nbu":
        await callback.answer()
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
    
        usd = next(x for x in data if x["cc"] == "USD")
        eur = next(x for x in data if x["cc"] == "EUR")
    
        await callback.message.answer(
            f"🏦 Офіційний курс НБУ:\n"
            f"💵 USD: {usd['rate']} грн\n"
            f"💶 EUR: {eur['rate']} грн\n"
            f"📅 {usd['exchangedate']}"
        )

    elif callback.data == "currency_market":
        await callback.answer()
        url = "https://api.monobank.ua/bank/currency"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
    
        usd = next(x for x in data if x["currencyCodeA"] == 840 and x["currencyCodeB"] == 980)
        eur = next(x for x in data if x["currencyCodeA"] == 978 and x["currencyCodeB"] == 980)
    
        await callback.message.answer(
            f"💱 Ринковий курс (Monobank):\n"
            f"💵 USD: купівля {usd['rateBuy']} / продаж {usd['rateSell']} грн\n"
            f"💶 EUR: купівля {eur['rateBuy']} / продаж {eur['rateSell']} грн"
        )
       
    elif callback.data == "about":
        await callback.answer()
        await callback.message.answer("ℹ️ Я учебный бот на aiogram 3")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())