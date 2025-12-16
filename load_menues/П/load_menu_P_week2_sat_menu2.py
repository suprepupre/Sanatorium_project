import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №2"   # "3"
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

    # перезаписываем только этот день (Сб, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Овощи отварные (капуста, горошек, морковь) с растит. маслом", "p": "7,2", "f": "10,0", "c": "4,1", "kcal": "135,0", "output": OUT(100)},
        {"name": "Творог с сахаром", "p": "1,56", "f": "0,00", "c": "16,50", "kcal": "70,20", "output": OUT(100)},
        {"name": "Каша рисовая молочная жидкая", "p": "3,5", "f": "5,7", "c": "25,9", "kcal": "168,2", "output": OUT(100 + 5)},
        {"name": "Абрикос (сушеный)", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста цветная запеченная с сыром под соусом (мука, молоко)", "p": "11,0", "f": "13,5", "c": "9,0", "kcal": "203,5", "output": OUT(150)},
        {"name": "Птица отварная, каша гречневая вязкая", "p": "20,7", "f": "16,8", "c": "22,7", "kcal": "378,3", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, гречневая каша вязкая", "p": "16,7", "f": "15,5", "c": "18,6", "kcal": "359,9", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон, масло), гречневая каша вязкая", "p": "9,5", "f": "10,2", "c": "13,3", "kcal": "364,2", "output": OUT(100 + 150)},
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
        {"name": "Салат из вареной моркови с растит. маслом", "p": "9,3", "f": "14,2", "c": "1,4", "kcal": "163,1", "output": OUT(100)},
        {"name": "Салат из свеклы со сметаной", "p": "3,3", "f": "9,4", "c": "13,9", "kcal": "137,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп из овощей (вегетарианский) (картофель, морковь, лук)", "p": "2,1", "f": "7,2", "c": "13,2", "kcal": "123,6", "output": OUT(300)},
        {"name": "Суп картофельный с овсяными хлопьями «Геркулес»", "p": "4,8", "f": "8,4", "c": "19,2", "kcal": "157,5", "output": OUT(300)},
        {"name": "Суп картофельный с горохом", "p": "8,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},
        {"name": "Суп молочный с рисовой крупой", "p": "7,8", "f": "10,2", "c": "21,9", "kcal": "210,6", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Говядина отварная, каша ячневая вязкая", "p": "21,1", "f": "18,1", "c": "16,2", "kcal": "332,5", "output": OUT(75 + 150)},
        {"name": "Говядина отварная, каша рисовая рассыпчатая", "p": "22,3", "f": "22,9", "c": "15,3", "kcal": "427,2", "output": OUT(75 + 150)},
        {"name": "Голубцы, фаршированные овощами и рисом (капуста, морковь, томат, лук, мука)", "p": "2,6", "f": "5,9", "c": "12,3", "kcal": "283,3", "output": OUT(200)},
        {"name": "Зразы куриные паровые (яйцо, батон, молоко), рисовая рассыпчатая/соус", "p": "20,9", "f": "22,8", "c": "32,8", "kcal": "421,4", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (яйцо, батон, молоко), ячневая вязкая", "p": "20,8", "f": "24,7", "c": "37,3", "kcal": "541,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "13", "f": "9,2", "c": "1,9", "kcal": "141,4", "output": OUT(100)},
        {"name": "Салат из свеклы с растит. маслом", "p": "1,5", "f": "2,5", "c": "1,5", "kcal": "86,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой со сметаной", "p": "4,20", "f": "2,60", "c": "8,00", "kcal": "170,80", "output": OUT(200)},
        {"name": "Рыба отварная (хек, лук), гречневая каша вязкая", "p": "13,6", "f": "19,8", "c": "15,3", "kcal": "586,3", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (хек, лук), картофельное пюре", "p": "16,2", "f": "15,4", "c": "13,5", "kcal": "512,7", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), гречневая каша вязкая", "p": "16,6", "f": "58,7", "c": "10,8", "kcal": "644", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), перловая каша рассыпчатая", "p": "16,6", "f": "58,7", "c": "10,8", "kcal": "644", "output": OUT(100 + 150)},
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