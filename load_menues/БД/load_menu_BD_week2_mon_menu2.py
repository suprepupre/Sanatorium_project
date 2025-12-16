import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 1            # Понедельник


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # чистим мусор: "14," "44,,0" "19025" и т.п.
    s = s.replace(",,", ",").replace("..", ".")
    s = re.sub(r"[^0-9,.\-]", "", s).rstrip(",.")
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # Для БД: повышаем is_diet до True (никогда не понижаем)
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # нутриенты заполняем только если пусто (не перетираем вручную правленный справочник)
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
        name = r["name"]
        # Общие позиции (хлеб/чай/батон/масло) не делаем diet=True
        mark_diet = (not is_common)

        dish = get_or_create_dish(
            name,
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

    # Перезаписываем только этот день (Пн, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Молоко", "p": "0,4", "f": "0,0", "c": "20,6", "kcal": "84,0", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат «Морской» (краб. палочки, морская капуста, яйцо, лук) с майонезом",
         "p": "3,5", "f": "8,2", "c": "12,5", "kcal": "254,5", "output": OUT(100)},
        {"name": "Каша молочная гречневая", "p": "4,5", "f": "5,4", "c": "17,9", "kcal": "140,3", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12.5", "c": "2.4", "kcal": "185.8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет фаршированный мясом (говядина, масло, сметана, мука)",
         "p": "11,0", "f": "13,2", "c": "9,0", "kcal": "203,5", "output": OUT(200)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная",
         "p": "21,2", "f": "12,9", "c": "25,6", "kcal": "454,3", "output": OUT(100 + 150)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша гречневая рассыпчатая",
         "p": "24,6", "f": "11,5", "c": "22,9", "kcal": "516,8", "output": OUT(100 + 150)},
        {"name": "Свинина, тушеная с капустой",
         "p": "27.4", "f": "62.1", "c": "26.9", "kcal": "779.2", "output": OUT(100 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), каша гречневая рассыпчатая",
         "p": "20,1", "f": "27,5", "c": "15,3", "kcal": "553,9", "output": OUT(75 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), каша пшенная",
         "p": "19,8", "f": "27,5", "c": "16,4", "kcal": "557", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с курагой со сметаной", "p": "1,7", "f": "13,5", "c": "16,1", "kcal": "95,6", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров с растит. маслом", "p": "0,85", "f": "5,10", "c": "6,72", "kcal": "75,14", "output": OUT(100)},
        {"name": "С-т мясной по-солигорски (говядина, капуста, рис, морковь)", "p": "8.6", "f": "14.4", "c": "16", "kcal": "226.8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с фрикадельками (свин-гов)", "p": "11,3", "f": "8,2", "c": "21,0", "kcal": "207,1", "output": OUT(300)},
        {"name": "Суп картофельный с горохом", "p": "8,70", "f": "9,60", "c": "29,10", "kcal": "238,50", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста брокколи с сыром под соусом", "p": "1,0", "f": "16,0", "c": "15,1", "kcal": "124,2", "output": OUT(250)},
        {"name": "Вареники ленивые со сметаной (творог, яйцо, мука), без сахара", "p": "28,8", "f": "19,6", "c": "27,8", "kcal": "398,0", "output": OUT(190 + 25)},  # 19025
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), овощи отварные (капуста, морковь, горошек)", "p": "21,3", "f": "16,3", "c": "13,2", "kcal": "445,3", "output": OUT(100 + 150)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), каша пшеничная вязкая", "p": "23,6", "f": "13,2", "c": "23,8", "kcal": "585,5", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (батон, молоко, яйцо), овощи отварные (капуста, морковь, брокколи, фасоль)", "p": "13.1", "f": "15,9", "c": "10,9", "kcal": "272.3", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты с огурцом с растит. маслом", "p": "2,2", "f": "5,1", "c": "11,0", "kcal": "194,1", "output": OUT(100)},
        {"name": "Салат «Прибой» (морская капуста, огурец, яблоко, яйцо, майонез)", "p": "12,3", "f": "10,9", "c": "14,1", "kcal": "169,7", "output": OUT(100)},
        {"name": "Салат из свеклы с изюмом со сметаной", "p": "3,0", "f": "10,2", "c": "13,5", "kcal": "150,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная (картофель, морковь, капуста, лук, мука, яйцо) со сметаной", "p": "7,50", "f": "31,75", "c": "36,75", "kcal": "450,25", "output": OUT(250)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "9,2", "f": "26,5", "c": "21,3", "kcal": "456,1", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), перловая каша вязкая", "p": "19,3", "f": "22.8", "c": "16,4", "kcal": "310,9", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина без яйца, батон), картофельное пюре", "p": "21,0", "f": "36,1", "c": "11,8", "kcal": "452,8", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, картофельное пюре", "p": "13,6", "f": "19,7", "c": "10,8", "kcal": "458.4", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, перловая каша вязкая", "p": "22,6", "f": "8,9", "c": "14,6", "kcal": "433.9", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт б/с", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()