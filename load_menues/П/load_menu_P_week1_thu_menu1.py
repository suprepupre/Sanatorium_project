import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №1"   # "2"
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

    # перезаписываем только этот день (Чт, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "19,32", "f": "13,56", "c": "2,71", "kcal": "209,9", "output": OUT(80)},
        {"name": "Каша молочная пшенная", "p": "4,40", "f": "5,90", "c": "29,00", "kcal": "185,60", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "7,1", "f": "9,1", "c": "0,0", "kcal": "113,1", "output": OUT(30)},
        {"name": "Салат из вареных овощей (морковь, цветная капуста, горошек) с растит. маслом",
         "p": "2,2", "f": "3,6", "c": "5,5", "kcal": "61,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка творожная (яйцо, творог, манка) со сметаной", "p": "24,75", "f": "19,35", "c": "18,75", "kcal": "344,40", "output": OUT(150 + 20)},
        {"name": "Омлет драчена (мука)", "p": "22,20", "f": "30,40", "c": "11,20", "kcal": "403,00", "output": OUT(210)},
        {"name": "Сосиски отварные, каша овсяная вязкая", "output": OUT(100)},  # БЖУ/ккал не указаны
        {"name": "Тефтели с рисом в сметанном соусе (говядина, лук, молоко), каша овсяная",
         "p": "17,7", "f": "29,5", "c": "36,7", "kcal": "485,5", "output": OUT(115 + 150)},
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
        {"name": "Салат из отварной моркови со сметаной", "p": "1,20", "f": "6,10", "c": "16,6", "kcal": "123,60", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "6,40", "f": "4,60", "c": "2,70", "kcal": "65,90", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с хлопьями «Геркулес»", "p": "2,70", "f": "2,70", "c": "18,60", "kcal": "112,50", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо, молоко)", "p": "2,0", "f": "1,5", "c": "11,8", "kcal": "40,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Оладьи яблочные (яйцо, мука, молоко) со сметаной", "p": "15,86", "f": "54,60", "c": "41,60", "kcal": "657,80", "output": OUT(200 + 20)},
        {"name": "Птица отварная, каша рисовая вязкая", "p": "18,7", "f": "32,2", "c": "46,5", "kcal": "561,5", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша гречневая рассыпчатая", "p": "18.7", "f": "32.2", "c": "46.5", "kcal": "561", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (курица, молоко, яйцо), каша гречневая рассыпчатая", "p": "43", "f": "38,9", "c": "62,6", "kcal": "724", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (курица, молоко, яйцо), каша рисовая вязкая", "p": "43", "f": "38.9", "c": "62.6", "kcal": "724", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "1,40", "f": "5,10", "c": "8,00", "kcal": "81,60", "output": OUT(80)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "1,50", "f": "4,70", "c": "7,30", "kcal": "71,40", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Рыба отварная (горбуша, лук), каша пшеничная вязкая", "p": "29,5", "f": "26,8", "c": "27,9", "kcal": "463,3", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша, лук), картофельно-морковное пюре", "p": "32,9", "f": "31,7", "c": "45,5", "kcal": "594,4", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина без яйца, батон), картофельно-морковное пюре", "p": "24,1", "f": "17,7", "c": "26,5", "kcal": "363,6", "output": OUT(100 + 200)},
        {"name": "Фрикадельки паровые (говядина без яйца, батон), каша пшеничная вязкая", "p": "27,9", "f": "22,7", "c": "43,7", "kcal": "494,6", "output": OUT(100 + 200)},
        {"name": "Запеканка капустная с черносливом и яблоками со сметаной", "p": "8,00", "f": "10,50", "c": "16,00", "kcal": "337,00", "output": OUT(200)},
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