import aiosqlite
from datetime import datetime

DB_PATH = "bot.db"

async def init_db():
    """Создаёт таблицы если их нет. Вызывается при старте бота."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weather_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                city TEXT,
                requested_at TEXT
            )
        """)
        await db.commit()

async def add_user(user_id: int, username: str, first_name: str):
    """Сохраняет пользователя. Если уже есть — игнорирует."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().isoformat()))
        await db.commit()

async def add_weather_request(user_id: int, city: str):
    """Сохраняет запрос погоды."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO weather_requests (user_id, city, requested_at)
            VALUES (?, ?, ?)
        """, (user_id, city, datetime.now().isoformat()))
        await db.commit()

async def get_user_history(user_id: int, limit: int = 5):
    """Возвращает последние N городов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT city, requested_at FROM weather_requests
            WHERE user_id = ?
            ORDER BY requested_at DESC
            LIMIT ?
        """, (user_id, limit))
        return await cursor.fetchall()

async def get_user_stats(user_id: int):
    """Возвращает количество запросов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM weather_requests
            WHERE user_id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        return row[0]