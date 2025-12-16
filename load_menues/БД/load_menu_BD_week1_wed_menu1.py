import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 3            # Среда


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


def OUT(total):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # Для БД: повышаем is_diet до True (никогда не понижаем)
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # нутриенты/выход заполняем только если пусто (не перетираем)
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
        mark_diet = (not is_common)  # общие (хлеб/чай/батон/масло) не помечаем как diet

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

    # перезаписываем только этот день (Ср, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок томатный", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "12,7", "f": "30,1", "c": "1,90", "kcal": "176,60", "output": OUT(80)},
        {"name": "Салат из белокочанной капусты, огурцов и сладкого перца со сметаной", "p": "1,3", "f": "5,1", "c": "8,3", "kcal": "82,8", "output": OUT(100)},
        {"name": "Каша гречневая молочная", "p": "4,5", "f": "5,4", "c": "17,9", "kcal": "140,3", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с колбасой вареной (яйцо, молоко, масло)", "p": "9,1", "f": "14,5", "c": "2,4", "kcal": "191", "output": OUT(200)},
        {"name": "Биточки (говядина, без яйца, батон) паровые, каша пшенная вязкая", "p": "15,7", "f": "20,7", "c": "23,2", "kcal": "341,7", "output": OUT(100 + 150)},
        {"name": "Биточки (говядина, без яйца, батон) паровые, картофельно-морковное пюре", "p": "21,2", "f": "25,9", "c": "33,3", "kcal": "440,0", "output": OUT(100 + 150)},
        {"name": "Куры отварные, каша пшенная вязкая", "p": "20,3", "f": "16,4", "c": "15,2", "kcal": "311,5", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # "12:00 Йогурт без сахара" — добавляем как общее блюдо (в системе нет отдельного приёма пищи)
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Йогурт без сахара"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растительным маслом", "p": "1,4", "f": "3,6", "c": "9,5", "kcal": "69,6", "output": OUT(85)},
        {"name": "С-т «Солнышко» (яйцо, морская капуста, горошек, морковь, лук) со сметаной", "p": "3,0", "f": "6,1", "c": "3,4", "kcal": "76,9", "output": OUT(100)},
        {"name": "С-т мясной по-слуцки (свинина, горох, картофель, огурец конс., лук, морковь, яйцо), майонез", "p": "4,6", "f": "13,9", "c": "3,8", "kcal": "157,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Солянка (говядина, колбаса вар., колбаса с/к, огурец мар., томат. паста) со сметаной", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "53,2", "output": OUT(300)},
        {"name": "Суп картофельный с фасолью", "p": "1,9", "f": "5,1", "c": "12,6", "kcal": "111,0", "output": OUT(300)},
        {"name": "Суп картофельный с овсяными хлопьями «Геркулес»", "p": "3,8", "f": "4,2", "c": "11,9", "kcal": "110,6", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Фасоль стручковая запеченная с сыром под соусом", "p": "3,5", "f": "6,2", "c": "7,9", "kcal": "101,9", "output": OUT(250)},
        {"name": "Котлета «Вясковая» (свинина, говядина, мука, томат, лук, яйцо, чеснок), каша гречневая рассыпчатая/соус", "p": "18", "f": "29,1", "c": "32,4", "kcal": "502,4", "output": OUT(120 + 150)},
        {"name": "Кнели из птицы с рисом паровые, каша гречневая рассыпчатая/соус", "p": "23,0", "f": "26,9", "c": "31,1", "kcal": "461,5", "output": OUT(100 + 150)},
        {"name": "Поджарка из говядины, каша гречневая рассыпчатая", "p": "16,8", "f": "29,6", "c": "31,7", "kcal": "481,7", "output": OUT(75 + 150)},
        {"name": "Поджарка из говядины, каша пшеничная вязкая", "p": "14,5", "f": "30,4", "c": "22,0", "kcal": "481,7", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН (19:00) =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат «Прибой» (морская капуста, огурец, яблоко, яйцо, майонез)", "p": "13,4", "f": "16,0", "c": "1,6", "kcal": "202,7", "output": OUT(100)},
        {"name": "С-т из огурцов, помидоров и сладкого перца с растит. маслом", "p": "1,2", "f": "0,0", "c": "3,3", "kcal": "64,3", "output": OUT(100)},
        {"name": "Салат «Розовый» (морковь, свекла, яйцо, лук) со сметаной", "p": "5,9", "f": "8,7", "c": "4,3", "kcal": "113,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "3,7", "f": "8,1", "c": "15,1", "kcal": "144,7", "output": OUT(200)},
        {"name": "Рыба, запеченная в сметане с луком (горбуша), картофельное пюре", "p": "15,1", "f": "12,4", "c": "21,4", "kcal": "261,2", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в сметане с луком (горбуша), каша перловая рассыпчатая", "p": "16,1", "f": "12,5", "c": "29,4", "kcal": "297,7", "output": OUT(100 + 150)},
        {"name": "Голубцы с мясом и рисом в томатном соусе (говядина, рис, морковь, лук, мука, сметана)", "p": "4,9", "f": "10,1", "c": "8,9", "kcal": "149,8", "output": OUT(250 + 50)},
        {"name": "Шницель натуральный рубленый (свинина, сухари), картофельное пюре", "p": "21,4", "f": "49,9", "c": "21,3", "kcal": "580,3", "output": OUT(100 + 150)},
        {"name": "Шницель натуральный рубленый (свинина, сухари), каша перловая рассыпчатая", "p": "22,4", "f": "45,0", "c": "29,3", "kcal": "616,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5.6", "f": "6.4", "c": "8.2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=True)

    print("Готово:", daily_menu)

main()