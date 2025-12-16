import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 4            # Четверг
MARK_DIET = False        # для B не помечаем блюда как диетические


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    s = re.sub(r"[^0-9,.\-]", "", s).rstrip(",.")
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, _created = Dish.objects.get_or_create(name=name)

    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # не перетираем справочник: заполняем только пустые поля
    if dish.proteins is None and p is not None: dish.proteins = p
    if dish.fats is None and f is not None: dish.fats = f
    if dish.carbs is None and c is not None: dish.carbs = c
    if dish.kcal is None and kcal is not None: dish.kcal = kcal
    if dish.output is None and output is not None: dish.output = output

    dish.save()
    return dish


def add_block(daily_menu: DailyMenu, meal_time: str, category: str, rows, *, is_common: bool):
    order = 1
    for r in rows:
        dish = get_or_create_dish(
            r["name"],
            p=D(r.get("p")),
            f=D(r.get("f")),
            c=D(r.get("c")),
            kcal=D(r.get("kcal")),
            output=r.get("output"),
            mark_diet=MARK_DIET,
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

    # очищаем только этот день (Чт, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,4", "f": "0,0", "c": "10,0", "kcal": "40,7", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт", "output": None},  # в тексте "1"
        {"name": "Салат «Одуванчик» (сыр, яйцо, лук) с майонезом", "p": "3,0", "f": "6,1", "c": "3,4", "kcal": "16,9", "output": OUT(100)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "Каша манная молочная жидкая", "p": "3,5", "f": "5,7", "c": "25,9", "kcal": "168,2", "output": OUT(100 + 5)},
        {"name": "Творог с повидлом", "p": "17.2", "f": "12.6", "c": "3.1", "kcal": "195.3", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка творожно-морковная (манка, яйцо) со сметаной", "p": "12,4", "f": "11,7", "c": "14,3", "kcal": "208,5", "output": OUT(150 + 20)},
        {"name": "Пельмени отварные со сметаной", "p": "0.3", "f": "2.6", "c": "0.4", "kcal": "22.9", "output": OUT(225)},
        {"name": "Шницель натуральный рубленый (свинина), картофельно-фасолевое пюре", "p": "21,7", "f": "29,0", "c": "9,9", "kcal": "438,6", "output": OUT(75 + 150)},
        {"name": "Шницель натуральный рубленый (свинина), каша ячневая вязкая", "p": "21,8", "f": "29,2", "c": "14,2", "kcal": "457,8", "output": OUT(75 + 150)},
        {"name": "Рулет паровой (говядина, батон, яйца), картофельно-фасолевое пюре", "p": "16,0", "f": "54,1", "c": "16,4", "kcal": "328,0", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, батон, яйца), каша ячневая вязкая", "p": "16,1", "f": "21,9", "c": "20,7", "kcal": "347,2", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе растворимый"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растительным маслом", "p": "1,4", "f": "0,0", "c": "4,8", "kcal": "124,8", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, сладкого перца и огурца со сметаной", "p": "0.9", "f": "8.3", "c": "3.5", "kcal": "195", "output": OUT(100)},
        {"name": "Салат «Павлинка» (куры, сыр, яблоко, яйцо, майонез)", "p": "8.6", "f": "14.4", "c": "16", "kcal": "226.8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Рассольник (перловка, огурец мар., картофель) со сметаной", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "53,2", "output": OUT(300)},
        {"name": "Суп картофельный с овсяной крупой", "p": "0,9", "f": "0,9", "c": "6,2", "kcal": "37,5", "output": OUT(300)},
        {"name": "Суп молочный с гречкой", "p": "2,5", "f": "3,1", "c": "9,3", "kcal": "75,0", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Шницель из капусты со сметаной (молоко, мука, яйцо)", "p": "9,2", "f": "22,8", "c": "18", "kcal": "314", "output": OUT(153 + 20)},  # как в тексте 153/20
        {"name": "Фрикадельки паровые (говядина), макароны отварные/соус", "p": "16,0", "f": "16,1", "c": "31,3", "kcal": "349,9", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина), каша перловая вязкая", "p": "14,1", "f": "15,2", "c": "21,4", "kcal": "292,9", "output": OUT(100 + 150)},
        {"name": "Рулет картофельный со свининой под соусом", "p": "6,2", "f": "13,0", "c": "15,2", "kcal": "205,2", "output": OUT(260 + 20)},
        {"name": "Птица жареная (сметана), каша перловая вязкая", "p": "36,9", "f": "15,7", "c": "31,6", "kcal": "427,3", "output": OUT(100 + 150)},
        {"name": "Птица жареная (сметана), овощи отварные (капуста, морковь, горошек)", "p": "33,8", "f": "15,7", "c": "12,6", "kcal": "319,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Яйцо, фаршированное рыбными консервами", "p": "3,8", "f": "14,2", "c": "4,7", "kcal": "161,0", "output": OUT(100)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "2,1", "f": "3,5", "c": "14,7", "kcal": "93,0", "output": OUT(100)},
        {"name": "Салат из капусты, яблок и сыра с растит. маслом", "p": "1,4", "f": "7,6", "c": "6,2", "kcal": "97,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка из капусты и яблок со сметаной", "p": "4,7", "f": "8,6", "c": "9,2", "kcal": "129,6", "output": OUT(230)},
        {"name": "Рыбник (горбуша, лук, яйцо, молоко, батон), картофельное пюре", "p": "15,1", "f": "12,4", "c": "21,4", "kcal": "261,2", "output": OUT(100 + 150)},
        {"name": "Рыбник (горбуша, лук, яйцо, молоко, батон), гречневая каша вязкая", "p": "16,2", "f": "12,5", "c": "32,6", "kcal": "308,0", "output": OUT(100 + 150)},
        {"name": "Биточки особые (свинина, говядина, батон), картофельное пюре", "p": "15,9", "f": "23,0", "c": "26,4", "kcal": "380,7", "output": OUT(100 + 150)},
        {"name": "Биточки особые (свинина, говядина, батон), гречневая каша вязкая", "p": "16,2", "f": "22,0", "c": "25,6", "kcal": "414,3", "output": OUT(100 + 150)},
        {"name": "Поджарка из свинины, картофельное пюре", "p": "27,4", "f": "28,4", "c": "13,4", "kcal": "420,9", "output": OUT(75 + 150)},
        {"name": "Поджарка из свинины, гречневая каша вязкая", "p": "28,5", "f": "28,5", "c": "24,6", "kcal": "467,7", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Выпечка"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "6,2", "f": "5,6", "c": "8,0", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()