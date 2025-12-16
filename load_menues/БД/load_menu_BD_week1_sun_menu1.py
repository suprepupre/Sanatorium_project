import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
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

    # Для БД: повышаем is_diet до True (никогда не понижаем)
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

    # перезаписываем только этот день (Вс, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,0", "c": "6,5", "kcal": "24,6", "output": OUT(200)},
        {"name": "Сок томатный",                "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",                      "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "17,1", "f": "12,5", "c": "2,4", "kcal": "185,8", "output": OUT(100)},
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0,0", "kcal": "377,0", "output": OUT(30)},
        {"name": "Салат из белокочанной капусты и перца со сметаной", "p": "1,9", "f": "5,8", "c": "9,4", "kcal": "90,3", "output": OUT(100)},
        {"name": "Салат «Одуванчик» (сыр, яйцо, лук) с майонезом", "p": "3,2", "f": "2,5", "c": "4,5", "kcal": "53,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста цветная запеченная с сыром под соусом (мука)", "p": "3,4", "f": "6,9", "c": "7,7", "kcal": "106,7", "output": OUT(180)},
        {"name": "Омлет с сыром (яйцо, молоко, сыр)", "p": "12,1", "f": "19,0", "c": "1,7", "kcal": "227,0", "output": OUT(200)},
        {"name": "Колбаса по-домашнему, картофельно-фасолевое пюре", "p": "39,8", "f": "37,0", "c": "9,9", "kcal": "702,6", "output": OUT(75 + 150)},
        {"name": "Колбаса по-домашнему, каша ячневая", "p": "37,7", "f": "37,2", "c": "14,2", "kcal": "721,8", "output": OUT(75 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца, мука), картофельно-фасолевое пюре", "p": "15,6", "f": "20,5", "c": "18,9", "kcal": "292,5", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца), каша ячневая вязкая", "p": "15,5", "f": "20,7", "c": "23,2", "kcal": "311,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай без сахара"},
        {"name": "Масло"},
    ], is_common=True)

    # 2-ой завтрак (12:00) — как общая категория внутри завтрака
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок без сахара"},
        {"name": "Яйцо отварное"},
        {"name": "Сок томатный"},
        {"name": "Яйцо отварное"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из помидоров и перца с растит. маслом", "p": "1,2", "f": "9,1", "c": "23,2", "kcal": "175,9", "output": OUT(100)},
        {"name": "Салат из моркови с изюмом со сметаной", "p": "1,6", "f": "3,5", "c": "19,7", "kcal": "107,7", "output": OUT(100)},
        {"name": "С-т из птицы с рисом (куры, кукуруза, яблоко, яйцо, майонез)", "p": "7,6", "f": "19,0", "c": "22,1", "kcal": "285,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ с капустой и картофелем (вегетарианский)", "p": "1,4", "f": "2,3", "c": "6,0", "kcal": "49,6", "output": OUT(300)},
        {"name": "Суп картофельный «Геркулес»", "p": "0,9", "f": "0,9", "c": "6,2", "kcal": "37,5", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Голубцы овощные с рисом в соусе", "p": "3,2", "f": "7,4", "c": "14,", "kcal": "134,8", "output": OUT(200)},
        {"name": "Сырники из творога запеченные (яйцо, мука, без сахара, манка) со сметаной", "p": "14,4", "f": "11,7", "c": "17,2", "kcal": "229,2", "output": OUT(150 + 20)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), овощи отварные (капуста, морковь, горошек)", "p": "27,2", "f": "27,7", "c": "6,0", "kcal": "381,7", "output": OUT(100 + 150)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), каша гречневая вязкая", "p": "28,5", "f": "28,7", "c": "15,0", "kcal": "433,9", "output": OUT(100 + 150)},
        {"name": "Зразы рубленые, фаршированные омлетом (говядина, яйцо, молоко, батон), каша гречневая вязкая", "p": "18,2", "f": "17,5", "c": "22,9", "kcal": "324,0", "output": OUT(100 + 150)},
        {"name": "Рагу из свинины (картофель, морковь, лук)", "p": "7,5", "f": "16,5", "c": "12,2", "kcal": "212,9", "output": OUT(75 + 200)},  # было 7,5,
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Компот без сахара"},
        {"name": "Хлеб"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,8", "f": "3,5", "c": "18,6", "kcal": "106,9", "output": OUT(100)},
        {"name": "Салат (морковь, яблоко, апельсин) с растит. маслом", "p": "1,4", "f": "3,6", "c": "9,5", "kcal": "69,6", "output": OUT(85)},
        {"name": "Яйцо, фаршированное рыбными консервами (рыб. консервы, майонез)", "p": "0,9", "f": "16,5", "c": "2,2", "kcal": "160,6", "output": OUT(85)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Оладьи картофельные (тёртый картофель, яйцо, лук) со сметаной", "p": "4,0", "f": "9,3", "c": "19,8", "kcal": "179,3", "output": OUT(200 + 20)},
        {"name": "Рулет паровой (говядина, батон, молоко, яйцо), картофельное пюре", "p": "15,4", "f": "19,5", "c": "21,0", "kcal": "324,7", "output": OUT(100 + 150)},
        {"name": "Рыба жареная в яйце (скумбрия, мука), овсяная каша вязкая", "p": "5,4", "f": "14,7", "c": "16,4", "kcal": "221,9", "output": OUT(100 + 150)},
        {"name": "Рыба жареная в яйце (скумбрия, мука), картофельное пюре", "p": "5,0", "f": "13,9", "c": "18,9", "kcal": "224,2", "output": OUT(100 + 150)},
        {"name": "Котлеты (свинина) рубленые жареные, картофельное пюре", "p": "12,9", "f": "38,2", "c": "28,9", "kcal": "518,0", "output": OUT(100 + 150)},  # было 100150
        {"name": "Котлеты (свинина) рубленые жареные, овсяная каша", "p": "13,3", "f": "39,0", "c": "26,5", "kcal": "515,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай без сахара"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()