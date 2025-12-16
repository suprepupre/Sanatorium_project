import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 6            # Суббота


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

    # перезаписываем только этот день (Сб, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из кураги без сахара", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Сок фруктовый без сахара", "p": "0.8", "f": "0", "c": "20", "kcal": "81.4", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "4,8", "f": "5,8", "c": "9,3", "kcal": "214,8", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, свежего огурца и зел. горошка с растит. маслом", "p": "5,50", "f": "19,30", "c": "6,10", "kcal": "225,20", "output": OUT(100)},
        {"name": "Салат из кукурузы с черносливом (кукуруза, сыр, чернослив, чеснок) с майонезом", "p": "8,3", "f": "23,9", "c": "1,6", "kcal": "254,1", "output": OUT(100)},
        {"name": "Каша молочная гречневая", "p": "10.1", "f": "9.4", "c": "0.6", "kcal": "142.7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста брокколи, запеченная с сыром под соусом (мука, сыр, молоко)", "p": "7,8", "f": "15,4", "c": "16,8", "kcal": "238,6", "output": OUT(200)},
        {"name": "Свинина по-домашнему (мука, сметана), картофельное пюре", "p": "25,1", "f": "63,3", "c": "22,6", "kcal": "440.7", "output": OUT(75 + 150)},
        {"name": "Свинина по-домашнему (мука, сметана), каша овсяная вязкая", "p": "25,9", "f": "63,3", "c": "24,5", "kcal": "453.8", "output": OUT(75 + 150)},
        {"name": "Птица отварная, картофельное пюре", "p": "20,7", "f": "46,5", "c": "20,1", "kcal": "584,4", "output": OUT(100 + 150)},  # 100150
        {"name": "Птица отварная, каша овсяная вязкая", "p": "17,3", "f": "25,3", "c": "12,0", "kcal": "419,4", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон, масло), каша овсяная вязкая", "p": "16,6", "f": "15,2", "c": "10,0", "kcal": "389,4", "output": OUT(100 + 200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # 2-ой завтрак — как общая категория внутри завтрака
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок без сахара"},
        {"name": "Печенье на фруктозе"},
        {"name": "Сок томатный"},
        {"name": "Печенье на фруктозе"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т из огурцов и помидоров с растит. маслом", "p": "2,3", "f": "10,5", "c": "8,9", "kcal": "112,2", "output": OUT(100)},
        {"name": "С-т из свеклы с курагой со сметаной", "p": "2.1", "f": "3.5", "c": "14.7", "kcal": "93.0", "output": OUT(100)},
        {"name": "С-т «Павлинка» (куры, сыр, морковь, яблоко, яйцо) с майонезом", "p": "14", "f": "24.6", "c": "3.5", "kcal": "288.6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп из овощей (брокколи, морковь, картофель, стручк. фасоль)", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Борщ сибирский (лук, томат) со сметаной", "p": "6,62", "f": "4,82", "c": "23,5", "kcal": "165,3", "output": OUT(300 + 30)},
        {"name": "Суп картофельный с овсяными хлопьями «Геркулес»", "p": "2,7", "f": "3,3", "c": "18,", "kcal": "117,9", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Зразы творожные (яйцо, мука, курага) со сметаной", "p": "22,2", "f": "10,0", "c": "12,4", "kcal": "312,6", "output": OUT(150 + 20)},
        {"name": "Сосиски отварные, каша перловая вязкая", "p": "19,4", "f": "27,5", "c": "41,9", "kcal": "499,6", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, перловая каша вязкая", "p": "28,4", "f": "19,0", "c": "11,7", "kcal": "330,2", "output": OUT(75 + 150)},
        {"name": "Говядина тушеная с черносливом (морковь, лук, томат), перловая каша вязкая", "p": "36,2", "f": "19,4", "c": "32,4", "kcal": "623,3", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из огурцов с растит. маслом", "p": "1,2", "f": "13,8", "c": "3,5", "kcal": "57,3", "output": OUT(100)},
        {"name": "С-т «Красная шапочка» (свекла, сыр, помидор, чеснок) с майонезом", "p": "4,50", "f": "14,50", "c": "7,30", "kcal": "176,70", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, яблок и моркови со сметаной", "p": "1,4", "f": "7,6", "c": "6,", "kcal": "97,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты со сметаной (молоко, мука, яйцо)", "p": "7,70", "f": "21", "c": "23", "kcal": "309,", "output": OUT(200 + 20)},  # 20020
        {"name": "Рыба, запеченная в майонезе (горбуша, лук), гречневая каша вязкая", "p": "22,8", "f": "20,8", "c": "23,1", "kcal": "293,4", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в майонезе (горбуша, лук), картофельно-морковное пюре", "p": "22,5", "f": "18,1", "c": "31,2", "kcal": "308,1", "output": OUT(100 + 150)},
        {"name": "Свинина отбивная по-лепельски (сыр, чеснок, лук, морковь), каша гречневая вязкая", "p": "20,1", "f": "34,1", "c": "24,6", "kcal": "440,3", "output": OUT(100 + 150)},
        {"name": "Свинина отбивная по-лепельски (сыр, чеснок, лук, морковь), картофельно-морковное пюре", "p": "19,0", "f": "33,4", "c": "12,9", "kcal": "384,5", "output": OUT(100 + 150)},  # 100150
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), гречневая каша вязкая", "p": "23,8", "f": "55,4", "c": "17,1", "kcal": "559,3", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), картофельно-морковное пюре", "p": "21,7", "f": "45,9", "c": "19", "kcal": "520,8", "output": OUT(100 + 150)},
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