import asyncio
from random import sample
import time
import json
import logging
import httpx
from bs4 import BeautifulSoup, soup
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
router = Router()

# ── Кеш категорій (TTL 6 годин) ──────────────────────────────────────────────
_categories_cache: dict | None = None
_categories_ts: float = 0
CATEGORIES_TTL = 6 * 3600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://www.rabotniki.ua"


# ── FSM ───────────────────────────────────────────────────────────────────────
class WorksState(StatesGroup):
    waiting_for_query = State()


# ── Клавіатура ────────────────────────────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ── Парсинг головної сторінки → {назва: url} ─────────────────────────────────
async def fetch_categories() -> dict[str, str]:
    global _categories_cache, _categories_ts

    if _categories_cache and (time.time() - _categories_ts) < CATEGORIES_TTL:
        return _categories_cache

    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        resp = await client.get(f"{BASE_URL}/uk/price")
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    logger.info(f"HTML отримано: {len(resp.text)} символів")
    logger.info(f"Знайдено посилань всього: {len(soup.select('ul li a[href]'))}")

    categories: dict[str, str] = {}

    sample = [a["href"] for a in soup.select("ul li a[href]")[:10]]
    logger.info(f"Приклад href: {sample}")

    for a in soup.select("ul li a[href]"):
        href = a["href"]
        name = a.get_text(strip=True)
        # беремо тільки внутрішні посилання на категорії (не фільтри, не сторінки)
        if (
            href.startswith("https://www.rabotniki.ua/uk/")
            and name
            and not any(x in href for x in ["/price", "/signup", "/login", "/tender",
                                             "/catalog", "/tenders", "/calculator",
                                             "/rabota", "/resume", "/faq", "/reklama",
                                             "/rules", "/agreement", "/about"])
        ):
            categories[name] = href

    logger.info(f"Категорій після фільтру: {len(categories)}")
    if categories:
        logger.info(f"Приклад: {list(categories.items())[:3]}")

    _categories_cache = categories
    _categories_ts = time.time()
    logger.info(f"Завантажено {len(categories)} категорій робіт")
    return categories


# ── Парсинг сторінки категорії → список робіт з цінами ───────────────────────
async def fetch_category_prices(url: str) -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    works = []

    for li in soup.select("ul li:has(a[href*='/uk/price/'])"):
        name_tag = li.select_one("a")
        name = name_tag.get_text(strip=True) if name_tag else None
        if not name:
            continue

        text = li.get_text(" ", strip=True)

        # Діапазон цін: "500 - 1200 грн/м²"
        import re
        range_match = re.search(r"Діапазон цін:\s*([\d\s\-]+(?:грн[^\n]*)?)", text)
        avg_match = re.search(r"Середня ціна\s+([\d]+)\s+(грн[^\s]*)", text)

        price_range = range_match.group(1).strip() if range_match else "—"
        avg_price = f"{avg_match.group(1)} {avg_match.group(2)}" if avg_match else "—"

        works.append({
            "name": name,
            "range": price_range,
            "avg": avg_price,
        })

    return works


# ── Claude API: підбір категорій під запит ───────────────────────────────────
async def ask_claude_categories(query: str, categories: dict[str, str]) -> list[str]:
    cat_list = "\n".join(f"- {name}" for name in categories.keys())
    prompt = (
        f"Користувач шукає будівельні роботи: «{query}»\n\n"
        f"Ось список доступних категорій:\n{cat_list}\n\n"
        "Обери 2-3 найбільш підходящі категорії з цього списку і поверни ТІЛЬКИ JSON-масив "
        "з точними назвами категорій, без пояснень, без markdown. "
        "Приклад: [\"Плиточні роботи\", \"Чорнові роботи по підлозі\"]"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()

    data = resp.json()
    raw = data["content"][0]["text"].strip()

    # Clean up possible markdown fences
    raw = raw.strip("`").strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()

    chosen: list[str] = json.loads(raw)
    # Валідуємо — повертаємо тільки ті, що реально є в словнику
    return [c for c in chosen if c in categories]


# ── Форматування відповіді ────────────────────────────────────────────────────
def format_prices(category: str, works: list[dict]) -> str:
    if not works:
        return f"<b>{category}</b>\nЦіни не знайдено.\n"

    lines = [f"<b>📋 {category}</b>"]
    for w in works[:15]:  # не більше 15 позицій
        lines.append(
            f"  • {w['name']}\n"
            f"    Діапазон: {w['range']} | Середня: <b>{w['avg']}</b>"
        )
    return "\n".join(lines)


# ── Хендлери ─────────────────────────────────────────────────────────────────
@router.message(F.text == "🔍 Пошук робіт")
async def works_start(message: Message, state: FSMContext):
    await state.set_state(WorksState.waiting_for_query)
    await message.answer(
        "🔍 <b>Пошук цін на будівельні роботи</b>\n\n"
        "Опишіть, що потрібно зробити (українською або російською).\n"
        "Наприклад: <i>«хочу покласти кафель»</i> або <i>«зробити стяжку»</i>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(WorksState.waiting_for_query, F.text != "🏠 Головне меню")
async def works_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Будь ласка, введіть запит.")
        return

    await state.clear()
    status = await message.answer("⏳ Шукаю підходящі категорії робіт...")

    try:
        # 1. Отримуємо всі категорії
        categories = await fetch_categories()
        if not categories:
            await status.edit_text("❌ Не вдалося завантажити список категорій. Спробуйте пізніше.")
            return

        # 2. Claude підбирає потрібні
        await status.edit_text("🤖 Claude аналізує ваш запит...")
        chosen = await ask_claude_categories(query, categories)

        if not chosen:
            await status.edit_text(
                "😕 Не вдалося знайти підходящі категорії.\n"
                "Спробуйте переформулювати запит."
            )
            return

        # 3. Паралельно парсимо сторінки категорій
        await status.edit_text(f"📊 Збираю ціни по {len(chosen)} категорії(ях)...")
        tasks = [fetch_category_prices(categories[cat]) for cat in chosen]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. Формуємо відповідь
        await status.delete()
        await message.answer(
            f"🔎 За запитом <b>«{query}»</b> знайдено:",
            parse_mode="HTML",
        )

        for cat, result in zip(chosen, results):
            if isinstance(result, Exception):
                logger.error(f"Помилка парсингу {cat}: {result}")
                await message.answer(f"⚠️ <b>{cat}</b>: не вдалося завантажити ціни.", parse_mode="HTML")
            else:
                text = format_prices(cat, result)
                if text:
                    await message.answer(text, parse_mode="HTML")

        await message.answer(
            f"📌 Детальніше на rabotniki.ua/uk/price",
            reply_markup=main_menu_kb(),
        )

    except httpx.HTTPError as e:
        logger.error(f"HTTP помилка в works: {e}")
        await status.edit_text("❌ Помилка з'єднання з сайтом. Спробуйте пізніше.")
    except json.JSONDecodeError:
        logger.error("Claude повернув не валідний JSON")
        await status.edit_text("❌ Помилка аналізу запиту. Спробуйте ще раз.")
    except Exception as e:
        logger.error(f"Невідома помилка в works: {e}")
        await status.edit_text("❌ Щось пішло не так. Спробуйте пізніше.")