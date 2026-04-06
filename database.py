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
        # ── Кошториси ──
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estimates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                object_name TEXT NOT NULL,
                system_type TEXT NOT NULL,
                total_area  REAL,
                total_usd   REAL,
                total_uah   REAL,
                usd_rate    REAL,
                data_json   TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_estimates_user
            ON estimates(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_estimates_date
            ON estimates(created_at)
        """)
        await db.commit()


# ════════════════════════════════════════════════════════════
# ІСНУЮЧІ ФУНКЦІЇ (без змін)
# ════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════
# НОВІ ФУНКЦІЇ — КОШТОРИСИ
# ════════════════════════════════════════════════════════════

async def save_estimate(
    user_id: int,
    object_name: str,
    system_type: str,
    total_area: float,
    total_usd: float,
    total_uah: float,
    usd_rate: float,
    data_json: str
) -> int:
    """Зберігає кошторис в БД, повертає id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO estimates
                (user_id, created_at, object_name, system_type,
                 total_area, total_usd, total_uah, usd_rate, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            object_name,
            system_type,
            total_area,
            total_usd,
            total_uah,
            usd_rate,
            data_json
        ))
        await db.commit()
        return cursor.lastrowid


async def get_estimates(
    user_id: int,
    date_filter: str = None,
    name_filter: str = None,
    limit: int = 10
) -> list:
    """
    Отримує список кошторисів користувача.
    date_filter — рядок "ДД.ММ.РРРР"
    name_filter — частина назви об'єкту
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        query = "SELECT * FROM estimates WHERE user_id = ?"
        params = [user_id]

        if date_filter:
            try:
                dt = datetime.strptime(date_filter, "%d.%m.%Y")
                date_iso = dt.strftime("%Y-%m-%d")
                query += " AND DATE(created_at) = ?"
                params.append(date_iso)
            except ValueError:
                pass

        if name_filter:
            query += " AND object_name LIKE ?"
            params.append(f"%{name_filter}%")

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_estimate_by_id(estimate_id: int) -> dict | None:
    """Отримує один кошторис по id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM estimates WHERE id = ?",
            (estimate_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
