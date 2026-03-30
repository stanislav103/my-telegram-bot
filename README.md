# 🤖 Telegram-бот на aiogram 3 з Claude AI

Багатофункціональний Telegram-бот з парсингом даних у реальному часі та інтеграцією Claude AI для розумного пошуку цін на будівельні роботи. Задеплоєно на Railway з автоматичним деплоєм при `git push`.

## ✨ Функціонал

| Розділ | Опис |
|---|---|
| 🌤 Погода | Актуальна погода по місту через OpenWeather API |
| 💱 Курс валют | Офіційний курс НБУ + ринковий курс Monobank |
| ⛽ Ціни на пальне | Парсинг oilprice.com.ua з кешем 30 хвилин |
| 🔍 Пошук робіт | AI-пошук цін на будівельні роботи через Claude API |

## 🧠 Як працює пошук робіт

```
Користувач: "хочу утеплити фасад"
    ↓
Парсинг каталогу rabotniki.ua (~300+ категорій)
    ↓
Claude AI підбирає 2-3 релевантні категорії
    ↓
Паралельний парсинг цін по кожній категорії
    ↓
Відповідь з діапазоном цін, середньою вартістю і посиланням
```

## 🛠 Стек

- **Python 3.14** + **aiogram 3.26** — асинхронний Telegram-бот з FSM
- **aiosqlite 0.22** — зберігання даних користувачів
- **httpx 0.28** — асинхронні HTTP-запити
- **BeautifulSoup4 4.14** + **lxml 6.0** — парсинг сайтів
- **Anthropic Claude API** — AI-підбір категорій робіт
- **python-dotenv** — керування змінними оточення
- **Railway** — хостинг з автодеплоєм

## 📁 Структура

```
my_bot/
├── bot.py            # Точка входу, роутери, logging
├── config.py         # Змінні оточення через dotenv
├── database.py       # Ініціалізація SQLite
├── states.py         # FSM стани
├── requirements.txt
├── Procfile          # worker: python bot.py
└── handlers/
    ├── start.py      # Головне меню з inline-кнопками
    ├── weather.py    # Погода
    ├── currency.py   # Курс валют (НБУ + Monobank)
    ├── fuel.py       # Ціни на пальне з кешем
    └── works.py      # Пошук робіт (парсинг + Claude AI)
```

## 🚀 Запуск локально

```bash
git clone https://github.com/stanislav103/my-telegram-bot
cd my-telegram-bot

pip install -r requirements.txt

# Створи .env файл
cp .env.example .env
# Заповни своїми ключами

python bot.py
```

## ⚙️ Змінні оточення

```env
BOT_TOKEN=your_telegram_bot_token
WEATHER_API_KEY=your_openweather_key
ANTHROPIC_API_KEY=your_anthropic_key
```

На Railway змінні додаються через **Variables** у панелі сервісу — файл `.env` на проді не використовується.

## 📦 Деплой на Railway

```
1. Підключи репо до Railway
2. Додай змінні оточення у Variables
3. git push origin main → автодеплой
```