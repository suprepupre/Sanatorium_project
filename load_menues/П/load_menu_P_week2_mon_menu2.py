import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №2"   # "3"
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

    # перезаписываем только этот день (Пн, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Рыба (филе) отварная с овощным гарниром", "p": "16,4", "f": "1,9", "c": "2,9", "kcal": "95,0", "output": OUT(50 + 50)},
        {"name": "Каша молочная гречневая", "p": "4,5", "f": "5,4", "c": "17,9", "kcal": "140,3", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0", "kcal": "377", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "17,0", "f": "9,1", "c": "12,0", "kcal": "200,1", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет драчена", "p": "11,0", "f": "13,2", "c": "9,0", "kcal": "203,5", "output": OUT(200)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная вязкая", "p": "21,2", "f": "12,9", "c": "25,6", "kcal": "454,3", "output": OUT(100 + 150)},  # 100150
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша гречневая вязкая", "p": "24,6", "f": "11,5", "c": "22,9", "kcal": "516,8", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша гречневая вязкая", "p": "27", "f": "12", "c": "34,3", "kcal": "458,9", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша овсяная", "p": "23", "f": "10", "c": "30", "kcal": "444", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай без сахара"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из вареной капусты с растит. маслом", "p": "1,7", "f": "13,5", "c": "16,1", "kcal": "95,6", "output": OUT(100)},
        {"name": "Птица отварная с овощным гарниром", "p": "10,7", "f": "6,4", "c": "3,3", "kcal": "125,0", "output": OUT(50 + 50)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с горохом", "p": "2,7", "f": "2,7", "c": "18,6", "kcal": "112,5", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо, без муки)", "p": "6,3", "f": "9,9", "c": "38,1", "kcal": "267,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста брокколи с сыром под соусом", "p": "1,0", "f": "16,0", "c": "15,1", "kcal": "124,2", "output": OUT(150)},
        {"name": "Говядина отварная, овощи отварные (капуста, морковь, горошек)", "p": "21,3", "f": "16,3", "c": "13,2", "kcal": "445,3", "output": OUT(100 + 150)},
        {"name": "Говядина отварная, каша пшеничная вязкая", "p": "23,6", "f": "13,2", "c": "23,8", "kcal": "685,5", "output": OUT(100 + 150)},  # 100150
        {"name": "Зразы куриные паровые (батон, молоко, яйцо), овощи отварные (капуста, морковь, горошек)", "p": "13.1", "f": "15,9", "c": "10,9", "kcal": "272.3", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (батон, молоко, яйцо), каша пшеничная вязкая", "p": "14.2", "f": "16,9", "c": "23,7", "kcal": "347.3", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "12,8", "f": "6,9", "c": "7,3", "kcal": "144,8", "output": OUT(100)},
        {"name": "Салат из свеклы с изюмом со сметаной", "p": "3,0", "f": "10,2", "c": "13,5", "kcal": "150,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная (картофель, морковь, капуста, лук, мука, яйцо) со сметаной", "p": "7,50", "f": "31,75", "c": "36,75", "kcal": "450,25", "output": OUT(250)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "16,2", "f": "16,5", "c": "21,3", "kcal": "456,1", "output": OUT(100 + 200)},
        {"name": "Рыба отварная (горбуша), перловая каша вязкая", "p": "19,3", "f": "22.8", "c": "16,4", "kcal": "310,9", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина, батон), картофельное пюре", "p": "16,7", "f": "37", "c": "32", "kcal": "406", "output": OUT(100 + 150)},
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