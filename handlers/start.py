from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from database import add_user  # ← добавить

router = Router()

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌤 Погода", callback_data="weather")],
        [InlineKeyboardButton(text="💰 Курс валют", callback_data="currency")],
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ])

@router.message(Command("start"))
async def cmd_start(message: Message):
    await add_user(  # ← сохраняем юзера
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыбери раздел:",
        reply_markup=main_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Используй /menu для навигации.\n/history — история запросов\n/stats — твоя статистика")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("Выбери раздел:", reply_markup=main_keyboard())