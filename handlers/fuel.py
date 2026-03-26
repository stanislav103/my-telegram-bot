# handlers/fuel.py
import httpx
from bs4 import BeautifulSoup
from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

URL = "https://oilprice.com.ua/ru/odessa/"

async def get_fuel_prices() -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(URL, headers={
            "User-Agent": "Mozilla/5.0"
        })
    
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
    
    return "\n".join(lines)

@router.callback_query(F.data == "fuel")
async def callback_fuel(call: CallbackQuery):
    await call.message.answer("⏳ Загружаю цены...")
    text = await get_fuel_prices()
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()