import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
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
        # общие позиции (хлеб/чай/батон/масло/сахар и т.п.) не помечаем как diet=True
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

    # перезаписываем только этот день (Сб, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,8", "f": "0,0", "c": "20,0", "kcal": "81,4", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Яйцо отварное", "p": "19,32", "f": "13,56", "c": "2,71", "kcal": "209,95", "output": None},  # 1шт
        {"name": "Каша молочная «Геркулес»", "p": "3,90", "f": "5,90", "c": "13,90", "kcal": "124,00", "output": OUT(100 + 5)},
        {"name": "Творог со сметаной", "p": "5,50", "f": "19,30", "c": "6,10", "kcal": "225,20", "output": OUT(80)},
        {"name": "Салат из вареной моркови с растит. маслом", "p": "2,2", "f": "4,0", "c": "5,8", "kcal": "63,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста (брокколи) запеченная с сыром под соусом (мука, сыр, молоко)",
         "p": "29,04", "f": "45,60", "c": "4,08", "kcal": "544,80", "output": OUT(150)},
        {"name": "Котлеты паровые (говядина, батон, масло), каша овсяная вязкая",
         "p": "18,9", "f": "16", "c": "12", "kcal": "443", "output": OUT(100 + 150)},
        {"name": "Птица отварная, картофельное пюре",
         "p": "17,3", "f": "25,3", "c": "12,0", "kcal": "419,4", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша овсяная вязкая",
         "p": "16,6", "f": "15,2", "c": "10,0", "kcal": "389,4", "output": OUT(100 + 200)},
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
        {"name": "Птица отварная, овощной гарнир", "p": "12,8", "f": "1,8", "c": "3,4", "kcal": "98,6", "output": OUT(50 + 50)},
        {"name": "Салат из вареной капусты с растит. маслом", "p": "0,90", "f": "2,30", "c": "2,25", "kcal": "33,25", "output": OUT(100)},
        {"name": "Салат из свеклы со сметаной", "p": "2,30", "f": "11,70", "c": "15,20", "kcal": "97,00", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп из овощей (вегетарианский) (картофель, морковь, лук)", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Суп картофельный с овсяными хлопьями «Геркулес»", "p": "6,62", "f": "4,82", "c": "23,5", "kcal": "165,3", "output": OUT(300 + 30)},
        {"name": "Суп молочный с макаронами", "p": "8,70", "f": "9,60", "c": "29,10", "kcal": "238,50", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Зразы творожные (яйцо, мука, курага) со сметаной", "p": "22,2", "f": "10,0", "c": "12,4", "kcal": "312,6", "output": OUT(150 + 20)},
        {"name": "Говядина отварная (лук) без соуса, перловая каша", "p": "26,2", "f": "9,4", "c": "12,4", "kcal": "348,6", "output": OUT(75 + 150)},
        {"name": "Говядина отварная (лук) без соуса, каша рисовая рассыпчатая", "p": "27.6", "f": "10.3", "c": "14.6", "kcal": "352.4", "output": OUT(75 + 150)},
        {"name": "Сосиски отварные, каша рисовая рассыпчатая", "p": "28,86", "f": "17,2", "c": "56,6", "kcal": "493,3", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, перловая каша", "p": "29,4", "f": "27,5", "c": "41,9", "kcal": "499,6", "output": OUT(100 + 200)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "19,32", "f": "13,56", "c": "2,71", "kcal": "209,95", "output": OUT(100)},
        {"name": "Салат из вареных овощей (морковь, цветная капуста, горошек) с растит. маслом", "p": "1,20", "f": "3,50", "c": "6,90", "kcal": "60,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты со сметаной (молоко, мука, яйцо)", "p": "10,5", "f": "11,1", "c": "77,7", "kcal": "453,3", "output": OUT(150 + 20)},
        {"name": "Рыба отварная (хек, лук), гречневая каша вязкая", "p": "22,8", "f": "20,8", "c": "23,1", "kcal": "293,4", "output": OUT(100 + 200)},
        {"name": "Рыба отварная (хек, лук), картофельно-морковное пюре", "p": "22,5", "f": "18,1", "c": "31,2", "kcal": "308,1", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), гречневая каша вязкая", "p": "18,6", "f": "27,5", "c": "39,9", "kcal": "488,6", "output": OUT(120 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), картофельно-морковное пюре", "p": "19,1", "f": "25,2", "c": "35,1", "kcal": "510,3", "output": OUT(120 + 200)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефирный напиток", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()