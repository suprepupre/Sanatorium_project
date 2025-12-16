import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 5            # Пятница


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    s = s.replace(",,", ",").replace("..", ".")
    s = re.sub(r"[^0-9,.\-]", "", s).rstrip(",.")
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total: int | None):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # Для БД: повышаем is_diet до True (никогда не понижаем)
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # нутриенты/выход заполняем только если пусто
    if dish.proteins is None and p is not None: dish.proteins = p
    if dish.fats is None and f is not None: dish.fats = f
    if dish.carbs is None and c is not None: dish.carbs = c
    if dish.kcal is None and kcal is not None: dish.kcal = kcal
    if dish.output is None and output is not None: dish.output = output

    if created or mark_diet or any(v is not None for v in (p, f, c, kcal, output)):
        dish.save()

    return dish


def add_block(daily_menu: DailyMenu, meal_time: str, category: str, rows, *, is_common: bool):
    order = 1
    for r in rows:
        mark_diet = (not is_common)  # общие позиции не помечаем как diet=True

        dish = get_or_create_dish(
            r["name"],
            p=D(r.get("p")),
            f=D(r.get("f")),
            c=D(r.get("c")),
            kcal=D(r.get("kcal")),
            output=r.get("output"),
            mark_diet=mark_diet,
        )

        MenuItem.objects.create(
            daily_menu=daily_menu,
            meal_time=meal_time,
            category=category,
            dish=dish,
            order_index=order,
            is_common=is_common,
        )
        order += 1


@transaction.atomic
def main():
    cycle, _ = MenuCycle.objects.get_or_create(name=CYCLE_NAME, defaults={"days_count": 7})
    daily_menu, _ = DailyMenu.objects.get_or_create(
        cycle=cycle,
        day_index=DAY_INDEX,
        diet_kind=DIET_KIND,
    )

    # перезаписываем только этот день (Пт, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из чернослива без сахара", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат «Острый» (сыр, морковь, яйцо, чеснок) с майонезом", "p": "0,8", "f": "10,1", "c": "13,9", "kcal": "310,2", "output": OUT(100)},
        {"name": "Яйцо отварное", "output": None},  # 1шт
        {"name": "Творог со сметаной", "p": "0,5", "f": "0,2", "c": "6,3", "kcal": "26,7", "output": OUT(80)},
        {"name": "Сыр", "p": "24", "f": "30,5", "c": "0", "kcal": "377", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой со сметаной", "p": "6,6", "f": "12,", "c": "42,", "kcal": "298,", "output": OUT(200 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "26,3", "f": "20,1", "c": "9,9", "kcal": "324,3", "output": OUT(200)},
        {"name": "Птица жареная (сметана), картофельно-гороховое пюре", "p": "26,3", "f": "20,1", "c": "9,9", "kcal": "324,3", "output": OUT(100 + 150)},
        {"name": "Птица жареная (сметана), каша пшенная вязкая", "p": "17,5", "f": "16,4", "c": "14,9", "kcal": "276,9", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), каша пшенная вязкая", "p": "17,5", "f": "16,4", "c": "14,9", "kcal": "276,9", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), картофельно-гороховое пюре", "p": "19,1", "f": "21,6", "c": "39,3", "kcal": "436,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # 2-ой завтрак (в системе нет отдельного приёма пищи) — добавляем как общие позиции
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок без сахара"},
        {"name": "Вафли на фруктозе"},
        {"name": "Сок томатный"},
        {"name": "Вафли на фруктозе"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты с огурцом с растит. маслом", "p": "1,7", "f": "7,2", "c": "6,3", "kcal": "96,4", "output": OUT(100)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "1,7", "f": "3,5", "c": "13,8", "kcal": "86,9", "output": OUT(100)},
        {"name": "Салат «Лепельский» (куры, яйцо, сыр, майонез)", "p": "5,5", "f": "19,3", "c": "6,1", "kcal": "225,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Рассольник (перловка, огурец мар., картофель) со сметаной", "p": "3,0", "f": "2,7", "c": "23,1", "kcal": "132,0", "output": OUT(300 + 10)},
        {"name": "Суп картофельный с горохом", "p": "4,2", "f": "8,7", "c": "21,0", "kcal": "184,8", "output": OUT(300)},
        {"name": "Суп молочный с перловой крупой", "p": "9,0", "f": "9,9", "c": "27,9", "kcal": "236,1", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Говядина отварная под соусом, овощи отварные (капуста, морковь, горошек)", "p": "24,4", "f": "25,6", "c": "39,7", "kcal": "555,4", "output": OUT(75 + 200)},
        {"name": "Говядина отварная под соусом, каша гречневая вязкая", "p": "22,8", "f": "32,6", "c": "29,8", "kcal": "468,2", "output": OUT(75 + 150)},
        {"name": "Рулет паровой (говядина, яйцо), каша гречневая вязкая", "p": "27,3", "f": "25,1", "c": "33,3", "kcal": "419,8", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, яйцо), овощи отварные (капуста, морковь, горошек)", "p": "27,9", "f": "25,4", "c": "39,4", "kcal": "476,4", "output": OUT(100 + 200)},
        {"name": "Птица отварная, каша гречневая вязкая", "p": "11,0", "f": "26,1", "c": "11,8", "kcal": "552,8", "output": OUT(100 + 150)},
        {"name": "Птица отварная, овощи отварные (капуста, морковь, горошек)", "p": "35.2", "f": "26.8", "c": "11.3", "kcal": "419.3", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с яблоками со сметаной", "p": "2,10", "f": "3,50", "c": "14,7", "kcal": "93,00", "output": OUT(100)},
        {"name": "С-т из белокочанной и морской капусты с растит. маслом", "p": "1,0", "f": "20,5", "c": "4,1", "kcal": "205,2", "output": OUT(100)},
        {"name": "Яйцо, фаршированное сыром (чеснок, майонез)", "p": "9", "f": "22", "c": "3,7", "kcal": "243", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная со сметаной (капуста, морковь, картофель, лук, манка)", "p": "3,5", "f": "9,6", "c": "10,8", "kcal": "140,8", "output": OUT(200)},
        {"name": "Рыба запеченная в сметане (горбуша, морковь), ячневая каша вязкая", "p": "29,7", "f": "24", "c": "32,1", "kcal": "460", "output": OUT(100 + 150)},
        {"name": "Рыба запеченная в сметане (горбуша, морковь), картофельное пюре", "p": "32,1", "f": "36,9", "c": "18,9", "kcal": "510", "output": OUT(100 + 200)},
        {"name": "Филе из птицы, запеченное с сыром, картофельное пюре", "p": "17,", "f": "18,1", "c": "18,2", "kcal": "473,8", "output": OUT(90 + 200)},
        {"name": "Филе из птицы, запеченное с сыром, ячневая каша вязкая", "p": "17", "f": "17,3", "c": "12,5", "kcal": "398,3", "output": OUT(90 + 150)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), картофельное пюре", "p": "19,2", "f": "22,6", "c": "33,8", "kcal": "415,2", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), ячневая каша вязкая", "p": "21,5", "f": "30", "c": "48,1", "kcal": "547,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()