import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 3            # Среда


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

    # перезаписываем только этот день (Ср, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный",  "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,8", "f": "0,0", "c": "20,", "kcal": "81,4", "output": OUT(200)},
        {"name": "Молоко",        "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Яйцо отварное", "p": "1,3", "f": "1,7", "c": "2,1", "kcal": "92,4", "output": None},  # 1шт
        {"name": "Каша пшенная молочная", "p": "4,5", "f": "5,4", "c": "17,8", "kcal": "140,2", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0", "kcal": "377", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "10,4", "f": "12,3", "c": "12,5", "kcal": "227,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с сыром (молоко, яйцо, сыр)", "p": "18,60", "f": "33,80", "c": "3,40", "kcal": "378,40", "output": OUT(200)},
        {"name": "Запеканка рисовая с яблоками со сметаной", "p": "11,6", "f": "14,7", "c": "13,3", "kcal": "232,9", "output": OUT(200 + 20)},
        {"name": "Котлеты паровые (говядина, батон), каша овсяная", "p": "17,3", "f": "25,3", "c": "20", "kcal": "389,4", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон), макароны отварные, соус", "p": "24,6", "f": "11,5", "c": "22,9", "kcal": "416,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Рыба отварная (хек), овощной гарнир", "p": "10,4", "f": "12,3", "c": "12,5", "kcal": "127,5", "output": OUT(100)},
        {"name": "Салат из свеклы со сметаной", "p": "0,40", "f": "3,5", "c": "6,2", "kcal": "57,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с рисом", "p": "2,7", "f": "2,7", "c": "18,6", "kcal": "112,5", "output": OUT(300)},
        {"name": "Суп молочный с овощами (морковь, картофель, стручк. фасоль, капуста, без муки)", "p": "6,6", "f": "4,8", "c": "21,3", "kcal": "150,9", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "20,5", "f": "19,0", "c": "47,4", "kcal": "236,7", "output": OUT(200)},
        {"name": "Птица отварная, каша пшеничная", "p": "14,8", "f": "10", "c": "32,4", "kcal": "283,3", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша гречневая рассыпчатая", "p": "23,3", "f": "12,8", "c": "59,8", "kcal": "448,8", "output": OUT(100 + 150)},
        {"name": "Говядина отварная под соусом, каша гречневая рассыпчатая", "p": "29,2", "f": "34,4", "c": "37,5", "kcal": "430", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "10,4", "f": "12,3", "c": "12,5", "kcal": "127,5", "output": OUT(80)},
        {"name": "Салат из вареной моркови со сметаной", "p": "1,6", "f": "8,0", "c": "4,3", "kcal": "94,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Капуста (брокколи) с сыром под соусом", "p": "3,", "f": "6,9", "c": "7,7", "kcal": "106,", "output": OUT(250)},
        {"name": "Тефтели паровые (говядина, без яйца, без муки), перловая каша вязкая", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,82", "output": OUT(260)},
        {"name": "Тефтели паровые (говядина, без яйца, без муки), картофельное пюре", "p": "13,4", "f": "40,3", "c": "32,7", "kcal": "351,9", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "16,2", "f": "16,5", "c": "21,3", "kcal": "456,1", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, картофельное пюре", "p": "19,3", "f": "22.8", "c": "16,4", "kcal": "310,9", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Кондитерские изделия"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()