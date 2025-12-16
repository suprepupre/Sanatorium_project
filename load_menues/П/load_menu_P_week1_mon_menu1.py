import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 1            # Понедельник


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
        # общие позиции (хлеб/чай/батон/масло и т.п.) не помечаем как diet=True
        mark_diet = (not is_common)

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

    # перезаписываем только этот день (Пн, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из отварной моркови со сметаной", "p": "1,9", "f": "5,2", "c": "4,6", "kcal": "55,5", "output": OUT(100)},
        {"name": "Творог с сахаром", "p": "5,9", "f": "8,7", "c": "4,3", "kcal": "113,5", "output": OUT(100)},
        {"name": "Йогурт", "output": None},  # в тексте "1"
        {"name": "Сыр", "p": "4,1", "f": "1,5", "c": "5,9", "kcal": "57,0", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста (брокколи) с сыром под соусом", "p": "0,4", "f": "0,9", "c": "1,4", "kcal": "15,2", "output": OUT(250)},
        {"name": "Биточки паровые (говядина, батон, молоко), овсяная каша", "p": "24,8", "f": "24,9", "c": "23,8", "kcal": "385,1", "output": OUT(100 + 200)},
        {"name": "Биточки паровые (говядина, батон, молоко), ячневая каша", "p": "21,1", "f": "23,2", "c": "22,8", "kcal": "366,3", "output": OUT(100 + 150)},
        {"name": "Куры отварные, овсяная каша", "p": "22,5", "f": "31,6", "c": "29,9", "kcal": "396,8", "output": OUT(100 + 150)},
        {"name": "Куры отварные, ячневая каша", "p": "22.5", "f": "31.6", "c": "29.9", "kcal": "396.8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе растворимый с молоком и сахаром"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Птица отварная (филе), гарнир овощной", "p": "0,9", "f": "8,7", "c": "4,3", "kcal": "53,5", "output": OUT(100)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "2,2", "f": "3,6", "c": "5,8", "kcal": "63,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с хлопьями «Геркулес»", "p": "9,3", "f": "5,4", "c": "23,7", "kcal": "170,4", "output": OUT(300)},  # было 300/
        {"name": "Суп молочный с овощами (капуста, картофель, морковь)", "p": "3,3", "f": "9,9", "c": "38,1", "kcal": "267,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Сырники творожные со сметаной (яйцо, мука)", "p": "26,9", "f": "21,2", "c": "15,9", "kcal": "359,7", "output": OUT(150 + 20)},
        {"name": "Кнели паровые из говядины с рисом, макароны отварные", "p": "15,0", "f": "24,3", "c": "12,5", "kcal": "330,3", "output": OUT(140 + 150)},
        {"name": "Кнели паровые из говядины с рисом, каша гречневая вязкая", "p": "16,1", "f": "25,1", "c": "31,1", "kcal": "416,3", "output": OUT(140 + 150)},
        {"name": "Говядина отварная без соуса, каша гречневая вязкая", "p": "19,8", "f": "5,8", "c": "8,9", "kcal": "486,5", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот из сухофруктов"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растит. маслом", "p": "0,3", "f": "1,1", "c": "3,7", "kcal": "42,1", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "2,1", "f": "2,0", "c": "5,0", "kcal": "46,10", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12.5", "c": "2.4", "kcal": "185.8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Сосиски отварные, перловая каша вязкая", "p": "20,7", "f": "29,8", "c": "43,8", "kcal": "323,5", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (хек, лук), картофельное пюре", "p": "19,5", "f": "22,9", "c": "33,9", "kcal": "439,4", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), картофельное пюре", "p": "23,9", "f": "82,8", "c": "53,6", "kcal": "744,6", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), каша перловая вязкая", "p": "23,9", "f": "58,9", "c": "37,3", "kcal": "671,2", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()