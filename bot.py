import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, weather, currency, fuel, works, estimate
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(weather.router)
dp.include_router(currency.router)
dp.include_router(fuel.router)
dp.include_router(estimate.router)
dp.include_router(works.router)

async def main():
    await init_db()  # ← создаёт таблицы при запуске
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())