# handlers/estimate.py — хендлер кошторису фасадних робіт

import json
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import BufferedInputFile

from states_estimate import EstimateStates, HistoryStates
from estimate_config import SYSTEM_OPTIONS, THICKNESS_OPTIONS, PAINT_OPTIONS
from estimate_calculator import calc_estimate
from estimate_excel import generate_excel, get_filename
from currency_mono import get_usd_rate, format_rate_info
from database import save_estimate, get_estimates, get_estimate_by_id

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════
# ДОПОМІЖНІ ФУНКЦІЇ
# ══════════════════════════════════════════════════════════

def kb_system():
    """Кнопки вибору системи утеплення"""
    builder = InlineKeyboardBuilder()
    for key, name in SYSTEM_OPTIONS.items():
        builder.button(text=name, callback_data=f"sys_{key}")
    return builder.as_markup()


def kb_thickness():
    """Кнопки вибору товщини утеплювача"""
    builder = InlineKeyboardBuilder()
    for t in THICKNESS_OPTIONS:
        builder.button(text=f"{t} мм", callback_data=f"thick_{t}")
    builder.adjust(5)
    return builder.as_markup()


def kb_paint():
    """Кнопки вибору фарби"""
    builder = InlineKeyboardBuilder()
    for key, info in PAINT_OPTIONS.items():
        builder.button(
            text=f"{info['name']} (${info['price_usd']}/10л)",
            callback_data=f"paint_{key}"
        )
    builder.adjust(1)
    return builder.as_markup()


def kb_yes_no(prefix: str):
    """Кнопки Так/Ні"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так", callback_data=f"{prefix}_yes")
    builder.button(text="❌ Ні",  callback_data=f"{prefix}_no")
    return builder.as_markup()


def kb_confirm():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити і розрахувати", callback_data="estimate_confirm")
    builder.button(text="❌ Скасувати", callback_data="estimate_cancel")
    builder.adjust(1)
    return builder.as_markup()


async def show_summary_before_confirm(message: Message, data: dict):
    """Показує зведення введених даних перед розрахунком"""
    windows = data.get("windows", [])
    doors   = data.get("doors", [])
    sys_name = SYSTEM_OPTIONS[data["system_type"]]
    paint_name = PAINT_OPTIONS[data["paint_type"]]["name"]

    win_text = "\n".join(
        f"  {i+1}. {w['w']}×{w['h']} м" for i, w in enumerate(windows)
    ) or "  —"
    door_text = "\n".join(
        f"  {i+1}. {d['w']}×{d['h']} м" for i, d in enumerate(doors)
    ) or "  —"

    plane_text = "\n".join(
        f"  {i+1}. {a} м²" for i, a in enumerate(data.get("plane_areas", []))
    )

    text = (
        f"📋 <b>Перевірте дані перед розрахунком:</b>\n\n"
        f"🏗 <b>Об'єкт:</b> {data['object_name']}\n"
        f"🧱 <b>Система:</b> {sys_name} {data['insulation_thick']}мм\n"
        f"🎨 <b>Фарба:</b> {paint_name}\n"
        f"📐 <b>Висота будівлі:</b> {data['building_height']} м\n"
        f"📏 <b>Периметр:</b> {data['perimeter']} м\n"
        f"🔲 <b>Плоскості:</b>\n{plane_text}\n"
        f"📐 <b>Зовнішніх кутів:</b> {data['corner_count']} шт\n"
        f"🪟 <b>Вікна ({len(windows)} шт):</b>\n{win_text}\n"
        f"🚪 <b>Двері ({len(doors)} шт):</b>\n{door_text}\n"
        f"📦 <b>Глибина відкосів:</b> {data['reveal_depth']} м\n"
        f"🚚 <b>Доставка:</b> {data['delivery_uah']} грн\n"
        f"🏗 <b>Ліси:</b> {'Так' if data['need_scaffold'] else 'Ні'}\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb_confirm())


# ══════════════════════════════════════════════════════════
# СТАРТ КОШТОРИСУ
# ══════════════════════════════════════════════════════════

@router.message(F.text == "📊 Новий кошторис")
@router.message(F.text == "/smeta")
async def cmd_smeta(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(EstimateStates.object_name)
    await message.answer(
        "📋 <b>Розрахунок кошторису фасадних робіт (Ceresit)</b>\n\n"
        "Введіть назву об'єкту та адресу:\n"
        "<i>Наприклад: Капітальний ремонт фасаду школи №1, вул. Строителів 9</i>",
        parse_mode="HTML"
    )


@router.message(EstimateStates.object_name)
async def get_object_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 5:
        await message.answer("⚠️ Введіть повнішу назву (мінімум 5 символів)")
        return
    await state.update_data(object_name=name)
    await state.set_state(EstimateStates.system_type)
    await message.answer(
        "🧱 <b>Оберіть систему утеплення:</b>",
        parse_mode="HTML",
        reply_markup=kb_system()
    )


# ── Система утеплення ──
@router.callback_query(EstimateStates.system_type, F.data.startswith("sys_"))
async def get_system_type(cb: CallbackQuery, state: FSMContext):
    sys = cb.data.split("_")[1]
    await state.update_data(system_type=sys)
    await cb.message.edit_text(
        f"✅ Система: <b>{SYSTEM_OPTIONS[sys]}</b>\n\n"
        "📏 <b>Оберіть товщину утеплювача:</b>",
        parse_mode="HTML",
        reply_markup=kb_thickness()
    )
    await state.set_state(EstimateStates.insulation_thick)


# ── Товщина утеплювача ──
@router.callback_query(EstimateStates.insulation_thick, F.data.startswith("thick_"))
async def get_thickness(cb: CallbackQuery, state: FSMContext):
    thick = int(cb.data.split("_")[1])
    await state.update_data(insulation_thick=thick)
    await cb.message.edit_text(
        f"✅ Товщина: <b>{thick} мм</b>\n\n"
        "🎨 <b>Оберіть тип фарби:</b>",
        parse_mode="HTML",
        reply_markup=kb_paint()
    )
    await state.set_state(EstimateStates.paint_type)


# ── Тип фарби ──
@router.callback_query(EstimateStates.paint_type, F.data.startswith("paint_"))
async def get_paint_type(cb: CallbackQuery, state: FSMContext):
    paint = cb.data.split("_")[1]
    await state.update_data(paint_type=paint)
    await cb.message.edit_text(
        f"✅ Фарба: <b>{PAINT_OPTIONS[paint]['name']}</b>\n\n"
        "📐 <b>Введіть висоту будівлі (м):</b>\n"
        "<i>Наприклад: 12.5</i>",
        parse_mode="HTML"
    )
    await state.set_state(EstimateStates.building_height)


# ── Висота будівлі ──
@router.message(EstimateStates.building_height)
async def get_building_height(message: Message, state: FSMContext):
    try:
        h = float(message.text.replace(",", "."))
        if h <= 0 or h > 200:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть коректне значення висоти (наприклад: 12.5)")
        return
    await state.update_data(building_height=h)
    await state.set_state(EstimateStates.perimeter)
    await message.answer(
        "📏 <b>Введіть периметр будівлі (м):</b>\n"
        "<i>Наприклад: 48</i>",
        parse_mode="HTML"
    )


# ── Периметр ──
@router.message(EstimateStates.perimeter)
async def get_perimeter(message: Message, state: FSMContext):
    try:
        p = float(message.text.replace(",", "."))
        if p <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть коректне значення периметру (наприклад: 48)")
        return
    await state.update_data(perimeter=p)
    await state.set_state(EstimateStates.plane_count)
    await message.answer(
        "🔲 <b>Скільки плоскостей (фасадів) у будівлі?</b>\n"
        "<i>Наприклад: 4</i>",
        parse_mode="HTML"
    )


# ── Кількість плоскостей ──
@router.message(EstimateStates.plane_count)
async def get_plane_count(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n <= 0 or n > 20:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть ціле число від 1 до 20")
        return
    await state.update_data(plane_count=n, plane_areas=[], _plane_current=1)
    await state.set_state(EstimateStates.plane_areas)
    await message.answer(
        f"📐 <b>Плоскість 1 з {n}</b>\n"
        "Введіть площу плоскості в м² (загальна, без відрахування прорізів):\n"
        "<i>Наприклад: 120.5</i>",
        parse_mode="HTML"
    )


# ── Площі плоскостей (по одній) ──
@router.message(EstimateStates.plane_areas)
async def get_plane_areas(message: Message, state: FSMContext):
    try:
        area = float(message.text.replace(",", "."))
        if area <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть коректне значення площі (наприклад: 120.5)")
        return

    data = await state.get_data()
    areas = data.get("plane_areas", [])
    areas.append(area)
    current = data.get("_plane_current", 1) + 1
    total = data["plane_count"]

    await state.update_data(plane_areas=areas, _plane_current=current)

    if current <= total:
        await message.answer(
            f"📐 <b>Плоскість {current} з {total}</b>\n"
            "Введіть площу плоскості в м²:",
            parse_mode="HTML"
        )
    else:
        # Всі плоскості введено
        total_gross = sum(areas)
        await state.set_state(EstimateStates.corner_count)
        await message.answer(
            f"✅ Площа плоскостей введена. Загальна брутто площа: <b>{total_gross} м²</b>\n\n"
            "🔺 <b>Кількість зовнішніх кутів будівлі:</b>\n"
            "<i>Наприклад: 4</i>",
            parse_mode="HTML"
        )


# ── Кути будівлі ──
@router.message(EstimateStates.corner_count)
async def get_corner_count(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n < 0 or n > 50:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть ціле число від 0 до 50")
        return
    await state.update_data(corner_count=n)
    await state.set_state(EstimateStates.window_count)
    await message.answer(
        "🪟 <b>Кількість вікон:</b>\n"
        "<i>Введіть 0 якщо вікон немає</i>",
        parse_mode="HTML"
    )


# ── Кількість вікон ──
@router.message(EstimateStates.window_count)
async def get_window_count(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n < 0 or n > 200:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть ціле число від 0 до 200")
        return

    await state.update_data(window_count=n, windows=[], _win_current=1)

    if n == 0:
        await state.set_state(EstimateStates.door_count)
        await message.answer(
            "🚪 <b>Кількість дверей:</b>\n"
            "<i>Введіть 0 якщо дверей немає</i>",
            parse_mode="HTML"
        )
    else:
        await state.set_state(EstimateStates.window_sizes)
        await message.answer(
            f"🪟 <b>Вікно 1 з {n}</b>\n"
            "Введіть розміри: <b>ширина висота</b> (через пробіл, в метрах)\n"
            "<i>Наприклад: 1.2 1.4</i>",
            parse_mode="HTML"
        )


# ── Розміри вікон (по одному) ──
@router.message(EstimateStates.window_sizes)
async def get_window_sizes(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().replace(",", ".").split()
        w, h = float(parts[0]), float(parts[1])
        if w <= 0 or h <= 0 or w > 10 or h > 10:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "⚠️ Введіть два числа через пробіл: ширина і висота\n"
            "<i>Наприклад: 1.2 1.4</i>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    windows = data.get("windows", [])
    windows.append({"w": w, "h": h})
    current = data.get("_win_current", 1) + 1
    total = data["window_count"]

    await state.update_data(windows=windows, _win_current=current)

    if current <= total:
        await message.answer(
            f"🪟 <b>Вікно {current} з {total}</b>\n"
            "Введіть розміри: ширина висота (через пробіл):",
            parse_mode="HTML"
        )
    else:
        await state.set_state(EstimateStates.door_count)
        await message.answer(
            f"✅ Всі вікна введено.\n\n"
            "🚪 <b>Кількість дверей:</b>\n"
            "<i>Введіть 0 якщо дверей немає</i>",
            parse_mode="HTML"
        )


# ── Кількість дверей ──
@router.message(EstimateStates.door_count)
async def get_door_count(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n < 0 or n > 50:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть ціле число від 0 до 50")
        return

    await state.update_data(door_count=n, doors=[], _door_current=1)

    if n == 0:
        await state.set_state(EstimateStates.reveal_depth)
        await message.answer(
            "📦 <b>Глибина відкосів (м):</b>\n"
            "Натисніть Enter для стандартного значення 0.35м або введіть своє:",
            parse_mode="HTML",
            reply_markup=_kb_default_reveal()
        )
    else:
        await state.set_state(EstimateStates.door_sizes)
        await message.answer(
            f"🚪 <b>Двері 1 з {n}</b>\n"
            "Введіть розміри: <b>ширина висота</b> (через пробіл, в метрах)\n"
            "<i>Наприклад: 0.9 2.1</i>",
            parse_mode="HTML"
        )


# ── Розміри дверей (по одній) ──
@router.message(EstimateStates.door_sizes)
async def get_door_sizes(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().replace(",", ".").split()
        w, h = float(parts[0]), float(parts[1])
        if w <= 0 or h <= 0 or w > 5 or h > 5:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "⚠️ Введіть два числа через пробіл: ширина і висота\n"
            "<i>Наприклад: 0.9 2.1</i>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    doors = data.get("doors", [])
    doors.append({"w": w, "h": h})
    current = data.get("_door_current", 1) + 1
    total = data["door_count"]

    await state.update_data(doors=doors, _door_current=current)

    if current <= total:
        await message.answer(
            f"🚪 <b>Двері {current} з {total}</b>\n"
            "Введіть розміри: ширина висота (через пробіл):",
            parse_mode="HTML"
        )
    else:
        await state.set_state(EstimateStates.reveal_depth)
        await message.answer(
            f"✅ Всі двері введено.\n\n"
            "📦 <b>Глибина відкосів (м):</b>\n"
            "Стандарт 0.35м — або введіть своє значення:",
            parse_mode="HTML",
            reply_markup=_kb_default_reveal()
        )


def _kb_default_reveal():
    builder = InlineKeyboardBuilder()
    builder.button(text="📐 Стандарт 0.35 м", callback_data="reveal_default")
    return builder.as_markup()


@router.callback_query(EstimateStates.reveal_depth, F.data == "reveal_default")
async def reveal_default(cb: CallbackQuery, state: FSMContext):
    await state.update_data(reveal_depth=0.35)
    await cb.message.edit_text("✅ Глибина відкосів: <b>0.35 м</b>", parse_mode="HTML")
    await _ask_delivery(cb.message, state)


@router.message(EstimateStates.reveal_depth)
async def get_reveal_depth(message: Message, state: FSMContext):
    try:
        d = float(message.text.replace(",", "."))
        if d <= 0 or d > 2:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть значення від 0.1 до 2.0 метра")
        return
    await state.update_data(reveal_depth=d)
    await _ask_delivery(message, state)


async def _ask_delivery(message: Message, state: FSMContext):
    await state.set_state(EstimateStates.delivery_cost)
    await message.answer(
        "🚚 <b>Вартість доставки матеріалів (грн):</b>\n"
        "<i>Введіть 0 якщо доставка не потрібна</i>",
        parse_mode="HTML"
    )


# ── Доставка ──
@router.message(EstimateStates.delivery_cost)
async def get_delivery_cost(message: Message, state: FSMContext):
    try:
        cost = float(message.text.replace(",", "."))
        if cost < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введіть суму в гривнях (0 або більше)")
        return
    await state.update_data(delivery_uah=cost)
    await state.set_state(EstimateStates.need_scaffold)
    await message.answer(
        "🏗 <b>Потрібні будівельні ліси?</b>",
        parse_mode="HTML",
        reply_markup=kb_yes_no("scaffold")
    )


# ── Ліси ──
@router.callback_query(EstimateStates.need_scaffold, F.data.startswith("scaffold_"))
async def get_scaffold(cb: CallbackQuery, state: FSMContext):
    need = cb.data == "scaffold_yes"
    await state.update_data(need_scaffold=need)
    await cb.message.edit_text(
        f"✅ Ліси: <b>{'Так' if need else 'Ні'}</b>",
        parse_mode="HTML"
    )
    data = await state.get_data()
    await state.set_state(EstimateStates.confirm)
    await show_summary_before_confirm(cb.message, data)


# ══════════════════════════════════════════════════════════
# ПІДТВЕРДЖЕННЯ І РОЗРАХУНОК
# ══════════════════════════════════════════════════════════

@router.callback_query(EstimateStates.confirm, F.data == "estimate_confirm")
async def confirm_estimate(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("⏳ Розраховую кошторис, зачекайте...")

    data = await state.get_data()

    # Отримуємо курс
    usd_rate = await get_usd_rate()

    try:
        result = calc_estimate(data, usd_rate)
        excel_bytes = generate_excel(result)
        filename = get_filename(result)

        # Зберігаємо в БД
        await save_estimate(
            user_id=cb.from_user.id,
            object_name=result["object_name"],
            system_type=result["system_type"],
            total_area=result["facade_area"],
            total_usd=result["grand_total_usd"],
            total_uah=result["grand_total_uah"],
            usd_rate=usd_rate,
            data_json=json.dumps(result, ensure_ascii=False)
        )

        # Коротке резюме в чат
        rate_info = format_rate_info(usd_rate)
        summary = (
            f"✅ <b>Кошторис готовий!</b>\n\n"
            f"🏗 <b>{result['object_name']}</b>\n\n"
            f"📐 Площа фасаду: <b>{result['facade_area']} м²</b>\n"
            f"📦 Площа відкосів: <b>{result['reveal_area']} м²</b>\n\n"
            f"🔹 Матеріали: <b>${result['mat_total_usd']:,.2f}</b> "
            f"({result['mat_total_uah']:,.0f} грн)\n"
            f"🔹 Роботи: <b>${result['work_total_usd']:,.2f}</b> "
            f"({result['work_total_uah']:,.0f} грн)\n"
            f"🔹 Доставка: <b>{result['delivery_uah']:,.0f} грн</b>\n\n"
            f"💰 <b>РАЗОМ: ${result['grand_total_usd']:,.2f} "
            f"/ {result['grand_total_uah']:,.0f} грн</b>\n\n"
            f"ℹ️ {rate_info}"
        )
        await cb.message.answer(summary, parse_mode="HTML")

        # Відправляємо Excel
        await cb.message.answer_document(
            BufferedInputFile(excel_bytes, filename=filename),
            caption=f"📊 Детальний кошторис: {result['object_name']}"
        )

    except Exception as e:
        logger.error(f"Помилка розрахунку кошторису: {e}", exc_info=True)
        await cb.message.answer(
            "❌ Виникла помилка при розрахунку. Спробуйте ще раз /smeta"
        )

    await state.clear()


@router.callback_query(EstimateStates.confirm, F.data == "estimate_cancel")
async def cancel_estimate(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Розрахунок скасовано. Введіть /smeta щоб почати знову.")


# ══════════════════════════════════════════════════════════
# ІСТОРІЯ КОШТОРИСІВ
# ══════════════════════════════════════════════════════════

@router.message(F.text.in_({"/history", "📁 Історія кошторисів"}))
async def cmd_history(message: Message, state: FSMContext):
    await state.set_state(HistoryStates.filter_choice)
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Всі кошториси",     callback_data="hist_all")
    builder.button(text="📅 Фільтр по даті",    callback_data="hist_date")
    builder.button(text="🔍 Пошук по назві",    callback_data="hist_name")
    builder.adjust(1)
    await message.answer(
        "📁 <b>Історія кошторисів</b>\n\nОберіть спосіб пошуку:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(HistoryStates.filter_choice, F.data == "hist_all")
async def history_all(cb: CallbackQuery, state: FSMContext):
    await _show_estimate_list(cb.message, cb.from_user.id, state)


@router.callback_query(HistoryStates.filter_choice, F.data == "hist_date")
async def history_by_date(cb: CallbackQuery, state: FSMContext):
    await state.set_state(HistoryStates.filter_date)
    await cb.message.edit_text(
        "📅 Введіть дату у форматі <b>ДД.ММ.РРРР</b>\n"
        "<i>Наприклад: 01.04.2026</i>",
        parse_mode="HTML"
    )


@router.message(HistoryStates.filter_date)
async def history_filter_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("⚠️ Невірний формат. Введіть дату як ДД.ММ.РРРР")
        return
    await _show_estimate_list(message, message.from_user.id, state, date_filter=message.text.strip())


@router.callback_query(HistoryStates.filter_choice, F.data == "hist_name")
async def history_by_name(cb: CallbackQuery, state: FSMContext):
    await state.set_state(HistoryStates.filter_name)
    await cb.message.edit_text(
        "🔍 Введіть частину назви об'єкту для пошуку:",
        parse_mode="HTML"
    )


@router.message(HistoryStates.filter_name)
async def history_filter_name(message: Message, state: FSMContext):
    await _show_estimate_list(message, message.from_user.id, state, name_filter=message.text.strip())


async def _show_estimate_list(message: Message, user_id: int, state: FSMContext,
                               date_filter=None, name_filter=None):
    estimates = await get_estimates(user_id, date_filter=date_filter, name_filter=name_filter)

    if not estimates:
        await state.clear()
        await message.answer("📭 Кошторисів не знайдено.")
        return

    await state.set_state(HistoryStates.select_estimate)
    builder = InlineKeyboardBuilder()
    for est in estimates[:10]:  # максимум 10
        date_str = est["created_at"][:10]
        label = f"{date_str} | {est['object_name'][:25]} | {est['total_uah']:,.0f} грн"
        builder.button(text=label, callback_data=f"est_{est['id']}")
    builder.adjust(1)

    await message.answer(
        f"📋 Знайдено кошторисів: <b>{len(estimates)}</b>\nОберіть для повторного завантаження:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(HistoryStates.select_estimate, F.data.startswith("est_"))
async def history_select(cb: CallbackQuery, state: FSMContext):
    est_id = int(cb.data.split("_")[1])
    est = await get_estimate_by_id(est_id)

    if not est:
        await cb.message.answer("❌ Кошторис не знайдено")
        await state.clear()
        return

    await cb.message.edit_text("⏳ Генерую Excel...")

    result = json.loads(est["data_json"])
    excel_bytes = generate_excel(result)
    filename = get_filename(result)

    await cb.message.answer_document(
        BufferedInputFile(excel_bytes, filename=filename),
        caption=f"📊 Кошторис від {est['created_at'][:10]}: {est['object_name']}"
    )
    await state.clear()