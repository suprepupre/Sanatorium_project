import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 1            # Понедельник


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # чистим мусор вроде "14," или "300/" или "44,,0"
    s = s.replace(",,", ",").replace("..", ".")
    s = re.sub(r"[^0-9,.\-]", "", s).rstrip(",.")
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total):
    # Dish.output = одно число, поэтому 75/150 -> 225 и т.п.
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # Для диеты BD: повышаем is_diet до True (никогда не понижаем)
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # нутриенты заполняем только если пусто (не перетираем справочник)
    if dish.proteins is None and p is not None: dish.proteins = p
    if dish.fats is None and f is not None: dish.fats = f
    if dish.carbs is None and c is not None: dish.carbs = c
    if dish.kcal is None and kcal is not None: dish.kcal = kcal
    if dish.output is None and output is not None: dish.output = output

    # сохраняем только если что-то реально могло измениться
    if created or mark_diet or any(v is not None for v in (p, f, c, kcal, output)):
        dish.save()

    return dish


def add_block(daily_menu: DailyMenu, meal_time: str, category: str, rows, *, is_common: bool):
    order = 1
    for r in rows:
        name = r["name"]
        # Общие позиции НЕ делаем diet=True, чтобы хлеб/чай не стал "диетическим блюдом"
        mark_diet = (not is_common)

        dish = get_or_create_dish(
            name,
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

    # Стираем только этот день (Пн, Меню №1, Диета БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из кураги без сахара", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный",                "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко",                      "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Каша молочная гречневая", "p": "3,69", "f": "5,9", "c": "13,9", "kcal": "124", "output": OUT(100)},
        {"name": "С-т «Солнышко» (горох, лук, морковь, морск. капуста, яйцо) со смет.", "p": "0,5", "f": "5,1", "c": "6,9", "kcal": "74,2", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12.5", "c": "2.4", "kcal": "185.8", "output": OUT(80)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста цветная с сыром под соусом", "p": "6,75", "f": "3", "c": "8,2", "kcal": "86,75", "output": OUT(200)},
        {"name": "Омлет фаршированный мясом (говядина, масло, сметана, мука)", "p": "9.1", "f": "14.5", "c": "2.4", "kcal": "191", "output": OUT(210)},
        {"name": "Свинина тушеная (томат. паста), ячневая каша вязкая", "p": "20,3", "f": "16,4", "c": "15,2", "kcal": "311,5", "output": OUT(75 + 150)},
        {"name": "Свинина тушеная (томат. паста), картофельно-гороховое пюре", "p": "20,2", "f": "16,0", "c": "10,9", "kcal": "292,3", "output": OUT(75 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), ячневая каша вязкая", "p": "12,7", "f": "14,0", "c": "23,3", "kcal": "285,8", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), картофельно-гороховое пюре", "p": "12,6", "f": "13,8", "c": "19,1", "kcal": "266,6", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т «Лепельская загадка» (куры, морковь, огурец конс., лук, майонез)", "p": "6,0", "f": "27,0", "c": "5,7", "kcal": "292,7", "output": OUT(50 + 50)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "1,5", "f": "3,6", "c": "8,4", "kcal": "67,6", "output": OUT(100)},
        {"name": "Салат из моркови, яблок, яиц с растит. маслом", "p": "1,4", "f": "2,6", "c": "3,8", "kcal": "66,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "1,6", "f": "2,6", "c": "5,5", "kcal": "49,7", "output": OUT(300)},
        {"name": "Суп картофельный с хлопьями «Геркулес»", "p": "0,8", "f": "0,8", "c": "6,6", "kcal": "37,7", "output": OUT(300)},  # было "300/"
        {"name": "Суп молочный с овощами (брокколи, картофель, морковь)", "p": "2,0", "f": "1,5", "c": "4,8", "kcal": "40,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Сырники творожные со сметаной (без сахара, мука, яйцо)", "p": "14,4", "f": "11,7", "c": "17,2", "kcal": "229,2", "output": OUT(150 + 20)},
        {"name": "Птица тушеная в соусе (лук, морковь, томат. паста), каша гречневая рассыпчатая", "p": "16,0", "f": "38,1", "c": "53,9", "kcal": "625,2", "output": OUT(75 + 150)},
        {"name": "Птица тушеная в соусе (лук, морковь, томат. паста), овощи отварные (капуста, морковь, горошек)", "p": "15,2", "f": "32,6", "c": "47,6", "kcal": "470", "output": OUT(75 + 150)},
        {"name": "Кнели паровые из говядины с рисом, каша гречневая рассыпчатая/соус", "p": "16,1", "f": "25,1", "c": "31,0", "kcal": "416,3", "output": OUT(140 + 150)},
        {"name": "Кнели паровые из говядины с рисом, овощи отварные (капуста, морковь, горошек)", "p": "13", "f": "23", "c": "17", "kcal": "376", "output": OUT(140 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "С-т из помидоров и сладкого перца с растит. маслом", "p": "2,4", "f": "14", "c": "2,2", "kcal": "153", "output": OUT(100)},  # жиры "14,"
        {"name": "Яйцо рубленое со сметаной", "p": "17,3", "f": "12,1", "c": "2,4", "kcal": "189,6", "output": OUT(100)},
        {"name": "Винегрет овощной с сельдью (зел. горошек, картофель, морковь, конс. огурец, свекла)", "p": "2,8", "f": "10,2", "c": "8,1", "kcal": "141", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка капустная с яблоками со сметаной", "p": "4,7", "f": "8,6", "c": "9,2", "kcal": "129,6", "output": OUT(200 + 20)},
        {"name": "Рыба жареная (скумбрия, мука), каша перловая вязкая", "p": "19,9", "f": "9,8", "c": "16,8", "kcal": "235,8", "output": OUT(100 + 150)},
        {"name": "Рыба жареная (скумбрия, мука), картофельное пюре", "p": "20,0", "f": "10,3", "c": "17,1", "kcal": "242,5", "output": OUT(100 + 150)},
        {"name": "Бифштекс (говядина, свинина), картофельное пюре", "p": "25,9", "f": "23", "c": "29,4", "kcal": "392,9", "output": OUT(75 + 150)},
        {"name": "Бифштекс (говядина, свинина), каша перловая вязкая", "p": "25,8", "f": "18,1", "c": "31,7", "kcal": "381,5", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), картофельное пюре", "p": "12,2", "f": "14,4", "c": "22,4", "kcal": "293,1", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, batон, без яйца), каша перловая вязкая", "p": "12,1", "f": "14,4", "c": "22,1", "kcal": "286,4", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт б/с", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()