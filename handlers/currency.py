from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import httpx

router = Router()

@router.callback_query(F.data == "currency")
async def callback_currency(call: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Офіційний (НБУ)", callback_data="currency_nbu")],
        [InlineKeyboardButton(text="💱 Ринковий (Mono)", callback_data="currency_market")],
    ])
    await call.message.answer("Який курс показати?", reply_markup=keyboard)
    await call.answer()

@router.callback_query(F.data == "currency_nbu")
async def callback_nbu(call: CallbackQuery):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json")
        data = response.json()

    usd = next(x for x in data if x["cc"] == "USD")
    eur = next(x for x in data if x["cc"] == "EUR")

    await call.message.answer(
        f"🏦 Офіційний курс НБУ:\n"
        f"💵 USD: {usd['rate']} грн\n"
        f"💶 EUR: {eur['rate']} грн\n"
        f"📅 {usd['exchangedate']}"
    )
    await call.answer()

@router.callback_query(F.data == "currency_market")
async def callback_mono(call: CallbackQuery):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.monobank.ua/bank/currency")
        data = response.json()

    usd = next(x for x in data if x["currencyCodeA"] == 840 and x["currencyCodeB"] == 980)
    eur = next(x for x in data if x["currencyCodeA"] == 978 and x["currencyCodeB"] == 980)

    await call.message.answer(
        f"💱 Ринковий курс (Monobank):\n"
        f"💵 USD: купівля {usd['rateBuy']} / продаж {usd['rateSell']} грн\n"
        f"💶 EUR: купівля {eur['rateBuy']} / продаж {eur['rateSell']} грн"
    )
    await call.answer()

@router.callback_query(F.data == "about")
async def callback_about(call: CallbackQuery):
    await call.message.answer("ℹ️ Я учебный бот на aiogram 3")
    await call.answer()