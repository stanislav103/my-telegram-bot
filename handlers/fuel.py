import httpx
from bs4 import BeautifulSoup
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from datetime import datetime, timedelta

router = Router()

URL = "https://oilprice.com.ua/ru/odessa/"

# Кэш — просто два значения в памяти
_cache_text: str | None = None
_cache_time: datetime | None = None
CACHE_TTL = timedelta(minutes=30)  # живёт 30 минут


async def get_fuel_prices() -> str:
    global _cache_text, _cache_time

    # Если кэш свежий — возвращаем его
    if _cache_text and _cache_time and datetime.now() - _cache_time < CACHE_TTL:
        age = int((datetime.now() - _cache_time).total_seconds() / 60)
        return _cache_text + f"\n\n🕒 Обновлено {age} мин. назад"

    # Иначе — парсим заново
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(URL, headers={"User-Agent": "Mozilla/5.0"})

    soup = BeautifulSoup(response.text, "lxml")

    table = soup.find("table")
    if not table:
        return "❌ Не удалось получить цены"

    rows = table.find_all("tr")
    lines = ["⛽ *Цены на топливо в Одессе:*\n"]

    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        azs    = cols[0].text.strip()
        a95    = cols[3].text.strip()
        diesel = cols[5].text.strip()
        gas    = cols[6].text.strip()

        if azs and (a95 != "—" or diesel != "—"):
            lines.append(
                f"🏪 *{azs}*\n"
                f"  А-95: {a95} грн\n"
                f"  ДП: {diesel} грн\n"
                f"  Газ: {gas} грн\n"
            )

    _cache_text = "\n".join(lines)
    _cache_time = datetime.now()

    return _cache_text + f"\n\n🕒 Только что обновлено"


async def send_fuel(answer_func):
    """Общая логика отправки — используется и кнопкой и командой"""
    text = await get_fuel_prices()
    await answer_func("⏳ Загружаю цены...")
    await answer_func(text, parse_mode="Markdown")


@router.callback_query(F.data == "fuel")
async def callback_fuel(call: CallbackQuery):
    await call.message.answer("⏳ Загружаю цены...")
    text = await get_fuel_prices()
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()


@router.message(Command("fuel"))
async def cmd_fuel(message: Message):
    await message.answer("⏳ Загружаю цены...")
    text = await get_fuel_prices()
    await message.answer(text, parse_mode="Markdown")