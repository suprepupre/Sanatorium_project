import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 7            # Воскресенье


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

    # перезаписываем только этот день (Вс, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из чернослива без сахара", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной и сахаром", "p": "13,1", "f": "9,2", "c": "1,9", "kcal": "142,2", "output": OUT(80)},
        {"name": "Сыр", "p": "1,8", "f": "4,1", "c": "5,0", "kcal": "64,5", "output": OUT(100)},
        {"name": "Каша молочная рисовая", "p": "3,5", "f": "5,7", "c": "25,9", "kcal": "168,2", "output": OUT(100 + 5)},
        {"name": "Йогурт", "p": "1,8", "f": "4,1", "c": "5,0", "kcal": "64,5", "output": None},  # в тексте "1" (шт)
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста цветная запеченная с сыром под соусом (мука, молоко)", "p": "24,7", "f": "19,3", "c": "18,7", "kcal": "344,4", "output": OUT(180)},
        {"name": "Рыба отварная (горбуша), каша ячневая", "p": "12.1", "f": "19.0", "c": "1.7", "kcal": "227.0", "output": OUT(200)},
        {"name": "Биточки паровые (говядина, батон, без яйца), картофельно-гороховое пюре", "p": "20,1", "f": "24,8", "c": "54,2", "kcal": "528,3", "output": OUT(100 + 200)},
        {"name": "Биточки паровые (говядина, батон, без яйца), каша ячневая вязкая", "p": "19,3", "f": "32", "c": "18,9", "kcal": "436,11", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Какао с молоком"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Птица отварная, овощной гарнир", "p": "1,4", "f": "4,0", "c": "9,8", "kcal": "71,9", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "1,0", "f": "4,1", "c": "2,2", "kcal": "52,3", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с рисом", "p": "6,62", "f": "4,82", "c": "23,5", "kcal": "165,3", "output": OUT(300 + 25)},
        {"name": "Затирка с молоком (мука, яйцо)", "p": "9,9", "f": "10,2", "c": "33,3", "kcal": "264,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Голубцы овощные с рисом в соусе", "p": "4,20", "f": "2,6", "c": "8,0", "kcal": "10,8", "output": OUT(200)},
        {"name": "Сырники из творога запеченные (яйцо, мука, сахар, манка) со сметаной", "p": "5,51", "f": "14,69", "c": "14,08", "kcal": "207,16", "output": OUT(150 + 20)},
        {"name": "Говядина отварная, макароны отварные", "p": "24,3", "f": "49,8", "c": "18,4", "kcal": "587,4", "output": OUT(75 + 200)},
        {"name": "Фрикадельки паровые (говядина), каша гречневая вязкая", "p": "14,9", "f": "14,9", "c": "11,3", "kcal": "360,8", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина), макароны отварные", "p": "11,9", "f": "19,9", "c": "18,8", "kcal": "420,1", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Компот"},
        {"name": "Хлеб"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "19,3", "f": "13,5", "c": "2,7", "kcal": "209,9", "output": OUT(100)},
        {"name": "Салат из свеклы с растит. маслом", "p": "1,4", "f": "4,0", "c": "9,8", "kcal": "51,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Рыба отварная (скумбрия, лук), картофельное пюре", "p": "18,4", "f": "16,6", "c": "28,9", "kcal": "334,9", "output": OUT(100 + 200)},
        {"name": "Рыба отварная (скумбрия, лук), овсяная каша вязкая", "p": "19,6", "f": "18,1", "c": "31,8", "kcal": "476,3", "output": OUT(100 + 200)},
        {"name": "Рулет паровой (говядина, батон, молоко, яйцо), картофельное пюре", "p": "18,4", "f": "16,6", "c": "28,9", "kcal": "334,9", "output": OUT(100 + 200)},
        {"name": "Птица отварная, картофельное пюре", "p": "19,6", "f": "18,1", "c": "31,8", "kcal": "476,3", "output": OUT(100 + 200)},
        {"name": "Птица отварная, овсяная каша вязкая", "p": "20.1", "f": "17.4", "c": "30.8", "kcal": "451.4", "output": OUT(100 + 200)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Кондитерские изделия"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()