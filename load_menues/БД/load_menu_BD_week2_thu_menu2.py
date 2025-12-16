import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 4            # Четверг


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

    # перезаписываем только этот день (Чт, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок фруктовый без сахара", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,8", "f": "0,0", "c": "20,0", "kcal": "81,4", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,4", "kcal": "116,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт без сахара", "output": None},  # 1шт
        {"name": "Салат «Одуванчик» (сыр, яйцо, лук) с майонезом", "p": "2,3", "f": "8,3", "c": "9,6", "kcal": "129,3", "output": OUT(100)},
        {"name": "Яйцо отварное", "p": "19,3", "f": "13,5", "c": "2,7", "kcal": "209,9", "output": None},  # в тексте "1"
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12.5", "c": "2.4", "kcal": "185.8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка творожно-морковная (яйцо) со сметаной", "p": "14,3", "f": "11,2", "c": "8,2", "kcal": "348,8", "output": OUT(150 + 20)},
        {"name": "Шницель натуральный рубленый (свинина), картофельно-фасолевое пюре", "p": "16", "f": "22,9", "c": "54", "kcal": "757,2", "output": OUT(75 + 150)},
        {"name": "Шницель натуральный рубленый (свинина), каша ячневая вязкая", "p": "19,55", "f": "25,7", "c": "27,53", "kcal": "498", "output": OUT(75 + 150)},
        {"name": "Рулет паровой (говядина, батон, яйца), картофельно-фасолевое пюре", "p": "14,4", "f": "13,2", "c": "11,6", "kcal": "362,2", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, батон, яйца), каша ячневая вязкая", "p": "11,4", "f": "15,5", "c": "8,8", "kcal": "354,6", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
    ], is_common=True)

    # 2-ой завтрак (в системе нет отдельного приёма пищи) — добавляем как общие позиции
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок без сахара"},
        {"name": "Печенье на фруктозе"},
        {"name": "Сок томатный"},
        {"name": "Печенье на фруктозе"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растительным маслом", "p": "5,3", "f": "10,1", "c": "9,2", "kcal": "257,4", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, сладкого перца и огурца со сметаной", "p": "0.9", "f": "8.3", "c": "3.5", "kcal": "195", "output": OUT(100)},
        {"name": "Салат «Павлинка» (куры, сыр, яблоко, яйцо, майонез)", "p": "8.6", "f": "14.4", "c": "16", "kcal": "226.8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Рассольник (перловка, огурец мар., картофель) со сметаной", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Суп картофельный с овсяной крупой", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Суп молочный с гречкой", "p": "2.5", "f": "3.1", "c": "9.3", "kcal": "75", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Шницель из капусты со сметаной (молоко, мука, яйцо)", "p": "9,2", "f": "22,8", "c": "18", "kcal": "1314", "output": OUT(153 + 20)},
        {"name": "Фрикадельки паровые (говядина), овощи отварные (капуста, морковь, горошек)", "p": "19,1", "f": "8,8", "c": "17,3", "kcal": "246,8", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина), каша перловая вязкая", "p": "13,2", "f": "8,3", "c": "14,5", "kcal": "252,3", "output": OUT(100 + 150)},
        {"name": "Птица жареная (сметана), каша перловая вязкая", "p": "36,9", "f": "15,7", "c": "31,6", "kcal": "427,3", "output": OUT(100 + 150)},
        {"name": "Птица жареная (сметана), овощи отварные (капуста, морковь, горошек)", "p": "33,8", "f": "15,7", "c": "12,6", "kcal": "319,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Яйцо, фаршированное рыбными консервами", "p": "10,4", "f": "12,3", "c": "12,5", "kcal": "127,5", "output": OUT(100)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "1,6", "f": "4,2", "c": "9,5", "kcal": "75,5", "output": OUT(100)},
        {"name": "Салат из капусты, яблок и сыра с растит. маслом", "p": "2,5", "f": "6,2", "c": "8,5", "kcal": "173,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка из капусты и яблок со сметаной", "p": "7,2", "f": "31", "c": "39", "kcal": "462,7", "output": OUT(230)},
        {"name": "Рыбник (горбуша, лук, яйцо, молоко, батон), картофельное пюре", "p": "20,9", "f": "32,9", "c": "28,5", "kcal": "408,5", "output": OUT(100 + 200)},
        {"name": "Рыбник (горбуша, лук, яйцо, молоко, батон), гречневая каша вязкая", "p": "19,8", "f": "28,2", "c": "21,2", "kcal": "368,5", "output": OUT(100 + 200)},
        {"name": "Биточки особые (свинина, говядина, батон), картофельное пюре", "p": "15,9", "f": "23,0", "c": "26,4", "kcal": "380,7", "output": OUT(100 + 150)},
        {"name": "Биточки особые (свинина, говядина, батон), гречневая каша вязкая", "p": "16,2", "f": "22,0", "c": "25,6", "kcal": "414,3", "output": OUT(75 + 150)},
        {"name": "Поджарка из свинины, гречневая каша вязкая", "p": "12,6", "f": "12,8", "c": "15,3", "kcal": "359,3", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()