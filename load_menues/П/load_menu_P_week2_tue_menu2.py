import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 2            # Вторник


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

    # перезаписываем только этот день (Вт, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из вареной моркови с растит. маслом", "p": "1,6", "f": "4,7", "c": "11,6", "kcal": "86,0", "output": OUT(100)},
        {"name": "Абрикос сушеный (курага)", "p": "0", "f": "0", "c": "15", "kcal": "112", "output": OUT(30)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "Каша молочная рисовая", "p": "4,5", "f": "6,5", "c": "17,8", "kcal": "149,0", "output": OUT(105)},
        {"name": "Творог с повидлом", "p": "14.3", "f": "7.7", "c": "11.4", "kcal": "173.8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка из творога и моркови со сметаной (манка, яйцо)", "p": "20,1", "f": "17,7", "c": "12,6", "kcal": "286,9", "output": OUT(150 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко, без муки)", "p": "27,1", "f": "43,9", "c": "4,08", "kcal": "533,2", "output": OUT(200)},
        {"name": "Биточки паровые (говядина, батон, без яйца), картофельное пюре", "p": "21,4", "f": "26,2", "c": "46,1", "kcal": "425,3", "output": OUT(75 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца), овсяная каша вязкая", "p": "19,3", "f": "22,2", "c": "34,1", "kcal": "389,3", "output": OUT(75 + 150)},
        {"name": "Сосиски отварные, картофельное пюре", "p": "12,3", "f": "14,2", "c": "5,3", "kcal": "321,5", "output": OUT(200 + 20)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе с молоком"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Рыба отварная (филе), овощной гарнир", "p": "1,1", "f": "8,4", "c": "4,3", "kcal": "87,5", "output": OUT(50 + 50)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "0,6", "f": "8,6", "c": "1,6", "kcal": "57,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с фрикадельками (свин-гов, лук, без яйца)", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},
        {"name": "Суп картофельный овсяный с хлопьями «Геркулес»", "p": "6,9", "f": "7,2", "c": "21,3", "kcal": "174,6", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Котлеты морковные со сметаной (манка, мука, яйцо)", "p": "12,0", "f": "9,3", "c": "28,3", "kcal": "145,5", "output": OUT(150 + 20)},
        {"name": "Суфле паровое с рисом (говядина, яйцо), каша рисовая вязкая", "p": "24,6", "f": "24,4", "c": "50,5", "kcal": "507,2", "output": OUT(100 + 200)},
        {"name": "Суфле паровое с рисом (говядина, яйцо), гречневая каша рассыпчатая", "p": "22,7", "f": "22,4", "c": "11,1", "kcal": "351,7", "output": OUT(100 + 150)},
        {"name": "Куры отварные (лук), гречневая каша рассыпчатая", "p": "23,4", "f": "20,4", "c": "16,5", "kcal": "457,5", "output": OUT(75 + 200)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с растит. маслом", "p": "1,1", "f": "8,4", "c": "4,3", "kcal": "85,3", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "13,1", "f": "9,2", "c": "1,9", "kcal": "142,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "4,20", "f": "2,60", "c": "8,00", "kcal": "170,80", "output": OUT(200)},
        {"name": "Оладьи мучные с изюмом (яйцо, молоко) со сметаной", "p": "8,6", "f": "14,8", "c": "59,9", "kcal": "401,3", "output": OUT(200)},
        {"name": "Рыба отварная (скумбрия), овсяная каша вязкая", "p": "27,5", "f": "30,2", "c": "10,2", "kcal": "420,6", "output": OUT(100 + 200)},
        {"name": "Рыба отварная (скумбрия), картофельное пюре", "p": "27,5", "f": "30,2", "c": "10,2", "kcal": "420,6", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), овсяная каша", "p": "19,3", "f": "22.8", "c": "16,4", "kcal": "310,9", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые (говядина, батон, без яйца), картофельное пюре", "p": "21,0", "f": "36,1", "c": "11,8", "kcal": "452,8", "output": OUT(100 + 150)},
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