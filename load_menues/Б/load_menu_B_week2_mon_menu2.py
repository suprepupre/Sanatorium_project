import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3" в ваших файлах
DAY_INDEX = 1            # Понедельник
MARK_DIET = False        # для B не помечаем блюда как диетические


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # чистим мусор, чтобы "185.8" / "17,1" / "7,5," нормально парсились
    s = re.sub(r"[^0-9,.\-]", "", s).rstrip(",.")
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, _created = Dish.objects.get_or_create(name=name)

    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # не перетираем справочник: заполняем только пустые
    if dish.proteins is None and p is not None: dish.proteins = p
    if dish.fats is None and f is not None: dish.fats = f
    if dish.carbs is None and c is not None: dish.carbs = c
    if dish.kcal is None and kcal is not None: dish.kcal = kcal
    if dish.output is None and output is not None: dish.output = output

    dish.save()
    return dish


def add_block(daily_menu: DailyMenu, meal_time: str, category: str, rows, *, is_common: bool):
    order = 1
    for r in rows:
        dish = get_or_create_dish(
            r["name"],
            p=D(r.get("p")),
            f=D(r.get("f")),
            c=D(r.get("c")),
            kcal=D(r.get("kcal")),
            output=r.get("output"),
            mark_diet=MARK_DIET,
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

    # очищаем только этот день (Пн, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат «Морской» (краб. палочки, морская капуста, яйцо, лук) с майонезом",
         "p": "7,5", "f": "19,4", "c": "23,3", "kcal": "299,7", "output": OUT(100)},
        {"name": "Каша молочная гречневая", "p": "3,9", "f": "5,9", "c": "13,9", "kcal": "124,0", "output": OUT(100 + 5)},
        {"name": "Икра кабачковая", "p": "0,0", "f": "7,7", "c": "7", "kcal": "97,0", "output": OUT(100)},
        {"name": "Сыр", "p": "15,4", "f": "8,3", "c": "10,9", "kcal": "180,8", "output": OUT(30)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12.5", "c": "2.4", "kcal": "185.8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет фаршированный мясом (говядина, масло, сметана, мука)",
         "p": "9,9", "f": "16,1", "c": "1,8", "kcal": "191,8", "output": OUT(200)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная вязкая",
         "p": "18,3", "f": "7,8", "c": "22,6", "kcal": "232,5", "output": OUT(100 + 150)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша гречневая рассыпчатая",
         "p": "18,6", "f": "7,9", "c": "31,9", "kcal": "269,1", "output": OUT(100 + 150)},
        {"name": "Свинина, тушеная с капустой",
         "p": "27.4", "f": "62.1", "c": "26.9", "kcal": "779.2", "output": OUT(75 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), каша гречневая рассыпчатая",
         "p": "19,8", "f": "27,2", "c": "15,6", "kcal": "551,1", "output": OUT(75 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), каша пшенная вязкая",
         "p": "20,1", "f": "23,7", "c": "24,9", "kcal": "441,6", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе растворимый с молоком"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с курагой со сметаной", "p": "2,4", "f": "11,6", "c": "6,6", "kcal": "140,4", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров с растит. маслом", "p": "1,6", "f": "4,6", "c": "3,9", "kcal": "57,3", "output": OUT(100)},
        {"name": "С-т мясной по-солигорски (говядина, капуста, рис, морковь) с майонезом", "p": "4,9", "f": "10,5", "c": "12,8", "kcal": "170,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с фрикадельками (свинина-говядина)", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "33,2", "output": OUT(300)},
        {"name": "Суп картофельный с горохом", "p": "1,0", "f": "0,8", "c": "7,5", "kcal": "42,5", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо, без муки)", "p": "2,5", "f": "3,1", "c": "9,3", "kcal": "75,0", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста брокколи с сыром под соусом", "p": "2,8", "f": "3,4", "c": "16,9", "kcal": "109,2", "output": OUT(250)},
        {"name": "Вареники ленивые со сметаной (творог, сахар, яйцо, мука)", "p": "14,4", "f": "9,8", "c": "13,9", "kcal": "199,0", "output": OUT(190 + 25)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), овощи отварные (капуста, морковь, брокколи)", "p": "33,9", "f": "16,3", "c": "10,4", "kcal": "308,3", "output": OUT(100 + 150)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), каша пшеничная вязкая", "p": "34,7", "f": "17,0", "c": "19,7", "kcal": "327,7", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (батон, молоко, яйцо), овощи отварные (капуста, морковь, брокколи, фасоль)", "p": "17,1", "f": "16,5", "c": "13,9", "kcal": "271,8", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (батон, молоко, яйцо), каша пшеничная вязкая", "p": "17,9", "f": "17,2", "c": "23,2", "kcal": "321,3", "output": OUT(100 + 150)},
        {"name": "Блинчики с говядиной и яйцом с маслом", "p": "12.9", "f": "17.4", "c": "25.7", "kcal": "311.6", "output": OUT(140)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты с огурцом с растит. маслом", "p": "3,0", "f": "11,7", "c": "15,2", "kcal": "177,0", "output": OUT(100)},
        {"name": "Салат «Прибой» (морская капуста, огурец, яблоко, яйцо, майонез)", "p": "0,9", "f": "16,5", "c": "2,2", "kcal": "160,6", "output": OUT(100)},
        {"name": "Салат из свеклы с изюмом со сметаной", "p": "5,9", "f": "8,7", "c": "4,3", "kcal": "113,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная (картофель, морковь, капуста, лук, мука, яйцо) со сметаной", "p": "3,5", "f": "9,6", "c": "10,8", "kcal": "140,8", "output": OUT(250)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "20,4", "f": "5,0", "c": "13,8", "kcal": "181,2", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), перловая каша вязкая", "p": "18,3", "f": "4,5", "c": "13,5", "kcal": "174,5", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина без яйца, батон), картофельное пюре", "p": "4,9", "f": "10,1", "c": "8,9", "kcal": "149,9", "output": OUT(220)},
        {"name": "Свинина, запеченная с сыром, картофельное пюре", "p": "22,6", "f": "35,8", "c": "13,7", "kcal": "458.4", "output": OUT(75 + 150)},
        {"name": "Свинина, запеченная с сыром, перловая каша вязкая", "p": "22,5", "f": "35,3", "c": "13,4", "kcal": "433.9", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт", "p": "6,2", "f": "5,6", "c": "8,0", "kcal": "112", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()