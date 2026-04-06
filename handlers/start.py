from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import add_user
from handlers.works import works_start

router = Router()


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌤 Погода", callback_data="weather")],
        [InlineKeyboardButton(text="💰 Курс валют", callback_data="currency")],
        [InlineKeyboardButton(text="⛽ Топливо", callback_data="fuel")],
        [InlineKeyboardButton(text="🔍 Поиск работ", callback_data="works")],
        [InlineKeyboardButton(text="📊 Кошторис фасаду", callback_data="smeta")],
        [InlineKeyboardButton(text="📁 Історія кошторисів", callback_data="history")],
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ])


@router.message(Command("start"))
async def cmd_start(message: Message):
    await add_user(
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
    await message.answer(
        "Используй /menu для навигации.\n"
        "/smeta — новий кошторис фасаду\n"
        "/history — історія кошторисів\n"
        "/stats — твоя статистика"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("Выбери раздел:", reply_markup=main_keyboard())


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(call: CallbackQuery):
    await call.message.answer("Выбери раздел:", reply_markup=main_keyboard())
    await call.answer()


@router.callback_query(F.data == "works")
async def callback_works(call: CallbackQuery, state: FSMContext):
    await works_start(call.message, state)
    await call.answer()


@router.callback_query(F.data == "smeta")
async def callback_smeta(call: CallbackQuery, state: FSMContext):
    from handlers.estimate import cmd_smeta
    await cmd_smeta(call.message, state)
    await call.answer()


@router.callback_query(F.data == "history")
async def callback_history(call: CallbackQuery, state: FSMContext):
    from handlers.estimate import cmd_history
    await cmd_history(call.message, state)
    await call.answer()