# estimate_calculator.py — логіка розрахунку кошторису

import math
from estimate_config import (
    MATERIAL_PRICES_USD, WORK_PRICES_USD, CONSUMPTION,
    PAINT_OPTIONS, SYSTEM_OPTIONS
)


def calc_estimate(data: dict, usd_rate: float) -> dict:
    """
    Головна функція розрахунку кошторису.

    data — словник з введеними користувачем даними:
        system_type       : "eps" або "mw"
        insulation_thick  : товщина утеплювача в мм (50/80/100/120/150)
        paint_type        : "ct42", "ct48" або "ct54"
        building_height   : висота будівлі (м)
        perimeter         : периметр будівлі (м)
        plane_areas       : список площ плоскостей [float, ...]
        corner_count      : кількість зовнішніх кутів
        windows           : список {"w": float, "h": float}
        doors             : список {"w": float, "h": float}
        reveal_depth      : глибина відкосів (м)
        delivery_uah      : вартість доставки (грн)
        need_scaffold     : True/False

    usd_rate — курс долара до гривні

    Повертає dict з повним розрахунком.
    """

    sys = data["system_type"]          # "eps" або "mw"
    thick_m = data["insulation_thick"] / 1000.0  # мм → метри
    paint = data["paint_type"]
    h = data["building_height"]
    perimeter = data["perimeter"]
    windows = data["windows"]          # [{"w": 1.2, "h": 1.4}, ...]
    doors = data["doors"]
    reveal_depth = data["reveal_depth"]
    C = CONSUMPTION
    M = MATERIAL_PRICES_USD
    W = WORK_PRICES_USD

    # ══════════════════════════════════════════
    # 1. ПЛОЩІ
    # ══════════════════════════════════════════

    # Загальна площа плоскостей (брутто)
    gross_area = sum(data["plane_areas"])

    # Площа вікон і дверей
    windows_area = sum(win["w"] * win["h"] for win in windows)
    doors_area   = sum(d["w"] * d["h"] for d in doors)
    openings_area = windows_area + doors_area

    # Площа фасаду нетто (для матеріалів і робіт)
    facade_area = gross_area - openings_area

    # Площа лісів (брутто — з прорізами)
    scaffold_area = gross_area

    # Площа відкосів
    # Вікна: 3 сторони (2 висоти + 1 ширина) × глибина
    # Двері: 3 сторони (2 висоти + 1 ширина) × глибина
    reveal_area = 0.0
    for win in windows:
        sides = 2 * win["h"] + win["w"]
        reveal_area += sides * reveal_depth
    for d in doors:
        sides = 2 * d["h"] + d["w"]
        reveal_area += sides * reveal_depth

    # Погонаж відливів (ширина прорізу + 10см виліт)
    windowsill_lm = sum(win["w"] + 0.10 for win in windows)
    windowsill_lm += sum(d["w"] + 0.10 for d in doors)

    # Кутовий профіль (п.м.):
    # — кути будівлі: кількість кутів × висота
    # — відкоси вікон: 3 сторони кожного
    # — відкоси дверей: 3 сторони кожного
    corner_lm_building = data["corner_count"] * h
    corner_lm_windows  = sum(2 * win["h"] + win["w"] for win in windows)
    corner_lm_doors    = sum(2 * d["h"] + d["w"] for d in doors)
    corner_lm_total    = corner_lm_building + corner_lm_windows + corner_lm_doors

    # Привіконний профіль (п.м.) — тільки вікна, 3 сторони
    window_profile_lm  = sum(2 * win["h"] + win["w"] for win in windows)

    # Стартовий профіль — периметр будівлі
    start_profile_lm   = perimeter

    # ══════════════════════════════════════════
    # 2. МАТЕРІАЛИ
    # ══════════════════════════════════════════
    materials = []

    def add_mat(name, qty_raw, unit, price_usd, pack_size=None, pack_unit=None):
        """Додає позицію матеріалу. Якщо є pack_size — округлює до упаковок."""
        if pack_size:
            packs = math.ceil(qty_raw / pack_size)
            qty = packs
            u = pack_unit
        else:
            qty = math.ceil(qty_raw * 100) / 100  # округлення до 0.01
            u = unit
        total_usd = qty * price_usd
        total_uah = total_usd * usd_rate
        materials.append({
            "name": name,
            "qty": qty,
            "unit": u,
            "price_usd": price_usd,
            "total_usd": total_usd,
            "total_uah": total_uah,
        })
        return total_usd

    mat_total_usd = 0.0

    # CT 17 — ґрунтовка основи
    ct17_l = facade_area * C["ct17_per_m2"]
    mat_total_usd += add_mat(
        "Ґрунтовка CT 17 (підготовка основи)",
        ct17_l, "л", M["ct17"],
        pack_size=C["primer_bucket_l"], pack_unit="відро 10л"
    )

    # Клей кріплення
    glue_fix_kg = facade_area * C["glue_fix_per_m2"]
    if sys == "eps":
        mat_total_usd += add_mat(
            "Клей CT 83 (кріплення пінопласту)",
            glue_fix_kg, "кг", M["ct83"],
            pack_size=C["glue_bag_kg"], pack_unit="мішок 25кг"
        )
    else:
        mat_total_usd += add_mat(
            "Клей CT 190 (кріплення мінвати)",
            glue_fix_kg, "кг", M["ct190"],
            pack_size=C["glue_bag_kg"], pack_unit="мішок 25кг"
        )

    # Утеплювач основний (м³)
    ins_m2 = facade_area * C["insulation_factor"]
    ins_m3 = ins_m2 * thick_m
    if sys == "eps":
        mat_total_usd += add_mat(
            f"Пінопласт {data['insulation_thick']}мм (основний шар)",
            ins_m3, "м³", M["eps_main"]
        )
    else:
        mat_total_usd += add_mat(
            f"Мінвата {data['insulation_thick']}мм (основний шар)",
            ins_m3, "м³", M["mw_main"]
        )

    # Дюбелі
    if sys == "eps":
        dowels_qty = facade_area * C["dowels_eps_per_m2"]
        mat_total_usd += add_mat(
            "Дюбель-гриб (для пінопласту)",
            dowels_qty, "шт", M["dowel_eps"]
        )
    else:
        dowels_qty = facade_area * C["dowels_mw_per_m2"]
        mat_total_usd += add_mat(
            "Дюбель-гриб (для мінвати)",
            dowels_qty, "шт", M["dowel_mw"]
        )

    # Клей армування
    glue_arm_kg = facade_area * C["glue_arm_per_m2"]
    if sys == "eps":
        mat_total_usd += add_mat(
            "Клей CT 85 (армування пінопласту)",
            glue_arm_kg, "кг", M["ct85"],
            pack_size=C["glue_bag_kg"], pack_unit="мішок 25кг"
        )
    else:
        mat_total_usd += add_mat(
            "Клей CT 190 (армування мінвати)",
            glue_arm_kg, "кг", M["ct190"],
            pack_size=C["glue_bag_kg"], pack_unit="мішок 25кг"
        )

    # Стеклосітка основна
    mesh_m2 = facade_area * C["mesh_factor"]
    mat_total_usd += add_mat(
        "Стеклосітка фасадна 160г/м²",
        mesh_m2, "м²", M["mesh"]
    )

    # CT 16 — ґрунтовка під штукатурку
    ct16_kg = facade_area * C["ct16_per_m2"]
    mat_total_usd += add_mat(
        "Ґрунтовка CT 16 (під штукатурку)",
        ct16_kg, "кг", M["ct16"],
        pack_size=C["primer_bucket_l"], pack_unit="відро 10л"
    )

    # Декоративна штукатурка
    plaster_kg = facade_area * C["plaster_per_m2"]
    mat_total_usd += add_mat(
        "Декоративна штукатурка CT 35 «короїд»",
        plaster_kg, "кг", M["ct35"],
        pack_size=C["plaster_bag_kg"], pack_unit="мішок 25кг"
    )

    # Фарба
    paint_info = PAINT_OPTIONS[paint]
    paint_l = facade_area * C["paint_per_m2"]
    mat_total_usd += add_mat(
        f"Фарба {paint_info['name']}",
        paint_l, "л", paint_info["price_usd"],
        pack_size=paint_info["bucket_l"], pack_unit="відро 10л"
    )

    # ── ВІДКОСИ ──
    if reveal_area > 0:
        # Утеплювач відкосів (м³)
        rev_ins_m2 = reveal_area * C["reveal_insulation_factor"]
        rev_ins_m3 = rev_ins_m2 * C["reveal_thickness_m"]
        if sys == "eps":
            mat_total_usd += add_mat(
                "Пінопласт 30мм (відкоси)",
                rev_ins_m3, "м³", M["eps_reveal"]
            )
        else:
            mat_total_usd += add_mat(
                "Мінвата 30мм (відкоси)",
                rev_ins_m3, "м³", M["mw_reveal"]
            )

        # Сітка відкосів
        rev_mesh = reveal_area * C["reveal_mesh_factor"]
        mat_total_usd += add_mat(
            "Стеклосітка (відкоси)",
            rev_mesh, "м²", M["mesh"]
        )

    # ── ПРОФІЛІ ТА ВІДЛИВИ ──
    mat_total_usd += add_mat(
        "Кутовий профіль ПВХ з сіткою",
        corner_lm_total, "п.м.", M["corner_profile"]
    )
    mat_total_usd += add_mat(
        "Привіконний профіль",
        window_profile_lm, "п.м.", M["window_profile"]
    )
    mat_total_usd += add_mat(
        "Стартовий профіль алюмінієвий",
        start_profile_lm, "п.м.", M["start_profile"]
    )
    if windowsill_lm > 0:
        mat_total_usd += add_mat(
            "Відлив металевий",
            windowsill_lm, "п.м.", M["windowsill"]
        )

    # ══════════════════════════════════════════
    # 3. РОБОТИ
    # ══════════════════════════════════════════
    works = []

    def add_work(name, qty, unit, price_usd):
        total_usd = qty * price_usd
        total_uah = total_usd * usd_rate
        works.append({
            "name": name,
            "qty": round(qty, 2),
            "unit": unit,
            "price_usd": price_usd,
            "total_usd": total_usd,
            "total_uah": total_uah,
        })
        return total_usd

    work_total_usd = 0.0

    work_total_usd += add_work("Ґрунтування основи (CT 17)",         facade_area, "м²", W["primer_ct17"])
    work_total_usd += add_work("Приклейка утеплювача",                facade_area, "м²", W["glue_work"])
    work_total_usd += add_work("Дюбелювання",                         facade_area, "м²", W["dowel_work"])
    work_total_usd += add_work("Армування (сітка + клей)",            facade_area, "м²", W["mesh_work"])
    work_total_usd += add_work("Ґрунтування під штукатурку (CT 16)", facade_area, "м²", W["primer_ct16"])
    work_total_usd += add_work("Декоративна штукатурка",              facade_area, "м²", W["plaster_work"])
    work_total_usd += add_work("Покраска",                            facade_area, "м²", W["paint_work"])

    if reveal_area > 0:
        work_total_usd += add_work("Відкоси (утеплення + оздоблення)", reveal_area, "м²", W["reveals_work"])

    if windowsill_lm > 0:
        work_total_usd += add_work("Встановлення відливів",           windowsill_lm, "п.м.", W["windowsill_work"])

    if corner_lm_total > 0:
        work_total_usd += add_work("Встановлення кутових профілів",   corner_lm_total,   "п.м.", W["corner_work"])

    if window_profile_lm > 0:
        work_total_usd += add_work("Встановлення привіконних профілів", window_profile_lm, "п.м.", W["window_prof_work"])

    work_total_usd += add_work("Встановлення стартового профілю",     start_profile_lm, "п.м.", W["start_prof_work"])

    # Ліси
    scaffold_total_usd = 0.0
    if data["need_scaffold"]:
        scaffold_total_usd += add_work("Оренда лісів",    scaffold_area, "м²", W["scaffold_rent"])
        scaffold_total_usd += add_work("Монтаж лісів",    scaffold_area, "м²", W["scaffold_install"])
        scaffold_total_usd += add_work("Демонтаж лісів",  scaffold_area, "м²", W["scaffold_remove"])

    # ══════════════════════════════════════════
    # 4. ПІДСУМКИ
    # ══════════════════════════════════════════
    delivery_uah = data.get("delivery_uah", 0.0)
    delivery_usd = delivery_uah / usd_rate if usd_rate else 0.0

    mat_total_uah   = mat_total_usd * usd_rate
    work_total_uah  = work_total_usd * usd_rate
    scaffold_uah    = scaffold_total_usd * usd_rate

    grand_total_usd = mat_total_usd + work_total_usd + delivery_usd
    grand_total_uah = grand_total_usd * usd_rate

    return {
        # Вхідні дані (для збереження в БД і Excel)
        "object_name":      data["object_name"],
        "system_type":      sys,
        "system_name":      SYSTEM_OPTIONS[sys],
        "insulation_thick": data["insulation_thick"],
        "paint_type":       paint,
        "paint_name":       PAINT_OPTIONS[paint]["name"],
        "building_height":  h,
        "perimeter":        perimeter,
        "corner_count":     data["corner_count"],
        "window_count":     len(windows),
        "door_count":       len(doors),
        "need_scaffold":    data["need_scaffold"],

        # Площі
        "gross_area":       round(gross_area, 2),
        "facade_area":      round(facade_area, 2),
        "reveal_area":      round(reveal_area, 2),
        "scaffold_area":    round(scaffold_area, 2),
        "windowsill_lm":    round(windowsill_lm, 2),
        "corner_lm_total":  round(corner_lm_total, 2),
        "window_profile_lm":round(window_profile_lm, 2),
        "start_profile_lm": round(start_profile_lm, 2),

        # Матеріали і роботи
        "materials":        materials,
        "works":            works,

        # Фінанси
        "usd_rate":         usd_rate,
        "mat_total_usd":    round(mat_total_usd, 2),
        "mat_total_uah":    round(mat_total_uah, 2),
        "work_total_usd":   round(work_total_usd, 2),
        "work_total_uah":   round(work_total_uah, 2),
        "delivery_uah":     round(delivery_uah, 2),
        "delivery_usd":     round(delivery_usd, 2),
        "grand_total_usd":  round(grand_total_usd, 2),
        "grand_total_uah":  round(grand_total_uah, 2),
    }
