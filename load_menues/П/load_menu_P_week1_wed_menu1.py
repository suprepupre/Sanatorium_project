import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №1"   # "2"
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

    # перезаписываем только этот день (Ср, Меню №1, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из вареной моркови со сметаной", "p": "1,6", "f": "4,7", "c": "6,4", "kcal": "66,2", "output": OUT(100)},
        {"name": "Йогурт", "output": None},
        {"name": "Творог со сметаной", "p": "17,4", "f": "12,2", "c": "2,4", "kcal": "189,6", "output": OUT(80)},
        {"name": "Каша гречневая молочная", "p": "4,5", "f": "5,4", "c": "17,9", "kcal": "140,3", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "7,1", "f": "9,1", "c": "0,0", "kcal": "113,1", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка рисовая с яблоками со сметаной", "p": "6,75", "f": "3,00", "c": "8,25", "kcal": "86,75", "output": OUT(200)},
        {"name": "Омлет с колбасой вареной (яйцо, молоко, масло)", "p": "22,2", "f": "28,2", "c": "11,2", "kcal": "403,", "output": OUT(210)},
        # "100/1500" трактуем как 100/150
        {"name": "Биточки (говядина, без яйца, батон) паровые, каша пшенная вязкая", "p": "20,7", "f": "22,9", "c": "51,3", "kcal": "428,3", "output": OUT(100 + 150)},
        {"name": "Биточки (говядина, без яйца, батон) паровые, картофельно-морковное пюре", "p": "21,6", "f": "23,7", "c": "52,8", "kcal": "448", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша пшенная вязкая", "p": "20.3", "f": "16.4", "c": "15.2", "kcal": "311.5", "output": OUT(100 + 50)},  # 100/50
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т из свеклы с растит. маслом", "p": "1,4", "f": "5,9", "c": "0,9", "kcal": "95,0", "output": OUT(100)},
        {"name": "Птица (филе) отварная, овощной гарнир", "p": "9,7", "f": "14,5", "c": "17,2", "kcal": "237,6", "output": OUT(50 + 50)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с овсяными хлопьями «Геркулес»", "p": "3,8", "f": "4,2", "c": "11,9", "kcal": "110,6", "output": OUT(300)},
        {"name": "Суп молочный с рисом", "p": "6,6", "f": "4,8", "c": "21,3", "kcal": "150,9", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста брокколи с сыром под соусом", "p": "3.5", "f": "11,1", "c": "77,7", "kcal": "453,3", "output": OUT(150 + 20)},
        {"name": "Говядина отварная, каша гречневая рассыпчатая", "p": "20,9", "f": "12,2", "c": "10,1", "kcal": "294,6", "output": OUT(75 + 150)},
        {"name": "Кнели из птицы с рисом паровые, каша пшеничная вязкая", "p": "13,2", "f": "24,2", "c": "33,5", "kcal": "415,8", "output": OUT(75 + 150)},  # 75150
        {"name": "Кнели из птицы с рисом паровые, каша гречневая рассыпчатая", "p": "11,3", "f": "20,2", "c": "31,1", "kcal": "412,6", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Яйцо рубленое со сметаной", "p": "1,4", "f": "10,6", "c": "4,8", "kcal": "124,8", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "13,1", "f": "9,2", "c": "1,9", "kcal": "142,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "3,7", "f": "8,4", "c": "15,1", "kcal": "144,7", "output": OUT(200)},
        {"name": "Рыба отварная (хек), картофельное пюре", "p": "25,1", "f": "13,3", "c": "33,7", "kcal": "458,2", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (хек), каша перловая рассыпчатая", "p": "27,5", "f": "11,8", "c": "37,3", "kcal": "452,5", "output": OUT(100 + 150)},
        {"name": "Голубцы с мясом и рисом в томатном соусе (говядина, рис, морковь, лук, мука, сметана)", "p": "12,9", "f": "26,6", "c": "23,4", "kcal": "394", "output": OUT(250 + 50)},
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