import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
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

    # Для П: повышаем is_diet до True (никогда не понижаем)
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

    # перезаписываем только этот день (Чт, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,8", "f": "0,0", "c": "20,0", "kcal": "81,4", "output": OUT(200)},
        {"name": "Молоко",           "p": "5,6", "f": "6,4", "c": "9,4", "kcal": "116,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт", "output": None},  # 1шт
        {"name": "Салат из вареных овощей с раст. маслом (морковь, цв. капуста, горошек)", "p": "2,2", "f": "3,6", "c": "5,8", "kcal": "63,0", "output": OUT(100)},
        {"name": "Каша манная молочная жидкая", "p": "3,30", "f": "4,20", "c": "24,0", "kcal": "145,3", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "7,1", "f": "9,1", "c": "0,0", "kcal": "113,1", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка морковно-творожная (яйцо) со сметаной", "p": "14,3", "f": "11,2", "c": "8,2", "kcal": "348,8", "output": OUT(150 + 20)},
        {"name": "Рулет паровой (говядина, батон, яйца), каша овсяная вязкая", "p": "15,4", "f": "12,5", "c": "10,8", "kcal": "348,6", "output": OUT(100 + 150)},
        {"name": "Пельмени отварные со сметаной", "p": "18,8", "f": "20,9", "c": "33,7", "kcal": "638,7", "output": OUT(220)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Рыба (хек), овощной гарнир", "p": "1,", "f": "3,1", "c": "8,7", "kcal": "68,7", "output": OUT(100)},
        {"name": "Салат из свеклы с растит. маслом", "p": "0,8", "f": "5,1", "c": "6,7", "kcal": "75,1", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с перловой крупой", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Суп картофельный с овсяной крупой", "p": "6,0", "f": "6,6", "c": "24,0", "kcal": "177,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Говядина отварная, макароны отварные", "p": "4,68", "f": "5,85", "c": "1,90", "kcal": "151,5", "output": OUT(200)},
        {"name": "Сосиски отварные, макароны отварные/соус", "p": "19,3", "f": "22.8", "c": "16,4", "kcal": "310,9", "output": OUT(100 + 200)},
        {"name": "Фрикадельки куриные паровые (батон, молоко), макароны отварные", "p": "19,1", "f": "8,8", "c": "17,3", "kcal": "246,8", "output": OUT(100 + 150)},
        {"name": "Фрикадельки куриные паровые (батон, молоко), каша перловая вязкая", "p": "27,6", "f": "15,5", "c": "46,4", "kcal": "449,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "19,3", "f": "13,5", "c": "2,7", "kcal": "209,9", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "2,5", "f": "6,2", "c": "8,5", "kcal": "173,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка из капусты и яблок (морковь, изюм, яйцо, молоко)", "p": "7,2", "f": "31", "c": "39", "kcal": "462", "output": OUT(230)},
        {"name": "Птица отварная, картофельное пюре", "p": "14,4", "f": "13,2", "c": "11,6", "kcal": "362,2", "output": OUT(100 + 150)},
        {"name": "Птица отварная, гречневая каша", "p": "17,5", "f": "24,6", "c": "10,9", "kcal": "356,3", "output": OUT(100 + 150)},
        {"name": "Рыбник (хек, лук, яйцо, молоко, батон), картофельное пюре", "p": "34,7", "f": "28,2", "c": "51,1", "kcal": "597,5", "output": OUT(100 + 150)},
        {"name": "Рыбник (хек, лук, яйцо, молоко, батон), гречневая каша вязкая", "p": "24,75", "f": "19,35", "c": "18,75", "kcal": "344,40", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Выпечка"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()