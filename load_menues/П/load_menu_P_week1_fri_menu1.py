import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
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

    # Для П: повышаем is_diet до True (никогда не понижаем)
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

    # перезаписываем только этот день (Пт, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт", "p": "2,2", "f": "4,0", "c": "5,8", "kcal": "63,0", "output": OUT(100)},
        {"name": "Каша молочная манная", "p": "2,8", "f": "5,7", "c": "26,6", "kcal": "168,5", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "7,1", "f": "9,1", "c": "0,0", "kcal": "113,1", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "17,4", "f": "12,3", "c": "12,5", "kcal": "227,5", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой со сметаной", "p": "6,6", "f": "12,0", "c": "42,", "kcal": "298,", "output": OUT(200 + 20)},
        {"name": "Биточки паровые (говядина, батон, молоко), каша пшенная вязкая", "p": "17,5", "f": "16,4", "c": "14,9", "kcal": "276,9", "output": OUT(100 + 150)},
        {"name": "Пельмени отварные", "p": "19,1", "f": "21,6", "c": "39,3", "kcal": "436,7", "output": OUT(200 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "19,6", "f": "32,5", "c": "34,4", "kcal": "509", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Рыба отварная (скумбрия), овощной гарнир", "p": "7,9", "f": "12,1", "c": "1,2", "kcal": "138,6", "output": OUT(100)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "2,3", "f": "3,1", "c": "5,3", "kcal": "96,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный «Геркулес»", "p": "2,70", "f": "2,70", "c": "18,60", "kcal": "112,50", "output": OUT(300)},
        {"name": "Суп молочный с перловой крупой", "p": "9,0", "f": "9,9", "c": "27,9", "kcal": "236,1", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Котлеты морковные со сметаной (манка, мука, яйцо)", "p": "5,51", "f": "14,69", "c": "14,08", "kcal": "207,16", "output": OUT(150 + 20)},
        {"name": "Рулет паровой (говядина, яйцо), макароны отварные/соус", "p": "27,3", "f": "25,1", "c": "33,3", "kcal": "419,8", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, яйцо), овощи отварные (цв. капуста, морковь, горошек)", "p": "27,9", "f": "25,4", "c": "39,4", "kcal": "476,4", "output": OUT(100 + 200)},
        {"name": "Птица отварная, каша гречневая вязкая", "p": "24,4", "f": "25,6", "c": "39,7", "kcal": "555,4", "output": OUT(100 + 150)},
        {"name": "Птица отварная, макароны отварные", "p": "22,8", "f": "32,6", "c": "29,8", "kcal": "468,2", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из вареных овощей (цветная капуста, морковь, горошек) с растит. маслом", "p": "1,4", "f": "5,1", "c": "8,0", "kcal": "81,6", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "17.", "f": "12.3", "c": "12.5", "kcal": "227.5", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Рыба отварная (скумбрия), ячневая каша вязкая", "p": "29,7", "f": "24", "c": "32,1", "kcal": "460", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (скумбрия), картофельное пюре", "p": "32,1", "f": "36,9", "c": "18,9", "kcal": "510", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), картофельное пюре", "p": "19,2", "f": "22,6", "c": "33,8", "kcal": "415,2", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), ячневая каша вязкая", "p": "21,5", "f": "30", "c": "48,1", "kcal": "547,8", "output": OUT(100 + 150)},
        {"name": "Запеканка овощная со сметаной (капуста, морковь, картофель, лук, манка)", "p": "3.5", "f": "12,0", "c": "42,4", "kcal": "298,2", "output": OUT(150 + 20)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()