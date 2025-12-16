import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №2"   # "3"
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

    # перезаписываем только этот день (Пт, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной и сахаром", "p": "12,8", "f": "6,9", "c": "7,3", "kcal": "144,8", "output": OUT(80)},
        {"name": "Салат «Агенчик» (морковь, зел. горошек, лук) с растит. маслом", "p": "2,20", "f": "4,00", "c": "5,80", "kcal": "63,00", "output": OUT(100)},
        {"name": "Каша молочная «Геркулес»", "p": "3.9", "f": "5.8", "c": "13.6", "kcal": "124.6", "output": OUT(100)},
        {"name": "Сыр", "p": "7,1", "f": "9,1", "c": "0,0", "kcal": "113,1", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Морковь тушеная в сметане (мука)", "p": "2,7", "f": "22,7", "c": "7,2", "kcal": "124,5", "output": OUT(150)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "18,0", "f": "29,8", "c": "8,3", "kcal": "402,0", "output": OUT(160)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная вязкая", "p": "19,3", "f": "22", "c": "26,4", "kcal": "310,9", "output": OUT(100 + 150)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, картофельное пюре", "p": "25,5", "f": "25,3", "c": "27,3", "kcal": "412,3", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из вареной моркови со сметаной", "p": "3,0", "f": "6,1", "c": "3,4", "kcal": "76,9", "output": OUT(100)},
        {"name": "Птица отварная (филе) с овощным гарниром", "p": "10,7", "f": "6,4", "c": "3,3", "kcal": "125,0", "output": OUT(50 + 50)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с овсяной крупой", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо)", "p": "6,6", "f": "4,8", "c": "21,3", "kcal": "150,9", "output": OUT(300)},
        {"name": "Суп картофельный с рыбой (горбуша, томат)", "p": "2.7", "f": "10", "c": "11.4", "kcal": "144", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Говядина отварная (лук), каша гречневая вязкая", "p": "23,8", "f": "32,9", "c": "15,8", "kcal": "427,9", "output": OUT(75 + 150)},
        {"name": "Суфле паровое (куры, яйцо, мука), каша гречневая вязкая", "p": "21,3", "f": "10,3", "c": "30,4", "kcal": "296", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (куры, яйцо, мука), рис рассыпчатый/соус", "p": "20", "f": "9,5", "c": "44,7", "kcal": "387,5", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, каша гречневая вязкая", "p": "18,2", "f": "18,5", "c": "22,5", "kcal": "483,6", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растит. маслом", "p": "1,6", "f": "4,7", "c": "6,4", "kcal": "66,2", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "2,9", "f": "10,0", "c": "5,1", "kcal": "54,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная со сметаной (картофель, капуста, морковь, лук, яйцо, манка, мука)", "p": "3,5", "f": "11,7", "c": "16,75", "kcal": "250,3", "output": OUT(150 + 20)},
        {"name": "Рыба отварная (скумбрия), картофельно-морковное пюре", "p": "13,7", "f": "15,4", "c": "21", "kcal": "345,9", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (скумбрия), каша овсяная вязкая", "p": "15,6", "f": "17,3", "c": "21,6", "kcal": "358,1", "output": OUT(100 + 150)},
        {"name": "Куры отварные, каша овсяная вязкая", "p": "20.7", "f": "16.6", "c": "16.2", "kcal": "320.9", "output": OUT(100 + 150)},
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