# currency_mono.py — отримання курсу USD/UAH з API Монобанку

import aiohttp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MONO_API_URL = "https://api.monobank.ua/bank/currency"

# Код валюти ISO 4217
USD_CODE = 840
UAH_CODE = 980


async def get_usd_rate() -> float:
    """
    Отримує актуальний курс продажу USD/UAH з API Монобанку.
    Повертає float — курс в гривнях за 1 долар.
    У разі помилки повертає запасне значення 44.0
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MONO_API_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    logger.warning(f"Monobank API відповів {resp.status}, використовуємо запасний курс")
                    return 44.0

                data = await resp.json()

                for item in data:
                    if item.get("currencyCodeA") == USD_CODE and item.get("currencyCodeB") == UAH_CODE:
                        # rateSell — курс продажу (по якому банк продає USD, тобто ми платимо більше)
                        # rateBuy  — курс купівлі
                        # Для кошторису використовуємо rateSell як більш реалістичний
                        rate = item.get("rateSell") or item.get("rateCross", 44.0)
                        logger.info(f"Курс USD/UAH з Монобанку: {rate}")
                        return float(rate)

                logger.warning("USD/UAH не знайдено в відповіді Монобанку, використовуємо запасний курс")
                return 44.0

    except Exception as e:
        logger.error(f"Помилка при отриманні курсу Монобанку: {e}")
        return 44.0


def format_rate_info(rate: float) -> str:
    """Форматує рядок з інформацією про курс для Excel і повідомлень"""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    return f"Курс НБУ (Монобанк): 1 USD = {rate:.2f} грн станом на {now}"
