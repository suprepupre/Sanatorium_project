import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 7            # Воскресенье
MARK_DIET = False        # для B не помечаем блюда как диетические


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # вычищаем мусор (например "7,5," -> "7,5")
    s = re.sub(r"[^0-9,.\-]", "", s)
    s = s.rstrip(",.")
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

    # очищаем только этот день
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},  # было "103"
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной и сахаром", "p": "17,1", "f": "12,0", "c": "2,4", "kcal": "185,8", "output": OUT(80)},
        {"name": "Йогурт", "output": None},  # в тексте "1" (шт), граммы неизвестны
        {"name": "Салат из белокочанной капусты и помидора со сметаной", "p": "1,9", "f": "5,8", "c": "9,4", "kcal": "90,3", "output": OUT(100)},
        {"name": "Каша молочная рисовая", "p": "2,9", "f": "4,8", "c": "10,9", "kcal": "180,8", "output": OUT(100 + 5)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста белокочанная запеченная с сыром под соусом (мука, молоко)", "p": "3,4", "f": "6,9", "c": "7,7", "kcal": "106,7", "output": OUT(250)},
        {"name": "Рыба отварная (горбуша), каша ячневая", "p": "12,1", "f": "19,0", "c": "1,7", "kcal": "227,0", "output": OUT(100 + 150)},
        {"name": "Колбаса по-домашнему, картофельно-гороховое пюре", "p": "39,8", "f": "37,0", "c": "9,9", "kcal": "702,6", "output": OUT(75 + 150)},
        {"name": "Колбаса по-домашнему, каша ячневая вязкая", "p": "37,7", "f": "37,2", "c": "14,2", "kcal": "721,8", "output": OUT(75 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца, мука), картофельно-гороховое пюре", "p": "15,6", "f": "20,5", "c": "18,9", "kcal": "292,5", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца), каша ячневая вязкая", "p": "15,5", "f": "20,7", "c": "23,2", "kcal": "311,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты и огурца с растит. маслом", "p": "1,2", "f": "9,1", "c": "23,2", "kcal": "175,9", "output": OUT(100)},
        {"name": "Салат из моркови с изюмом со сметаной", "p": "1,6", "f": "3,5", "c": "19,7", "kcal": "107,7", "output": OUT(100)},
        {"name": "С-т «Лепельская загадка» (куры, морковь, огурец конс., лук, майонез)", "p": "7,6", "f": "19,0", "c": "22,1", "kcal": "285,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "1,4", "f": "2,3", "c": "6,0", "kcal": "49,6", "output": OUT(300)},
        {"name": "Суп картофельный с рисом", "p": "0,8", "f": "0,8", "c": "6,5", "kcal": "37,7", "output": OUT(300 + 25)},
        {"name": "Затирка с молоком (мука, яйцо)", "p": "3,3", "f": "3,4", "c": "11,1", "kcal": "88,1", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Голубцы овощные с рисом в соусе", "p": "3,2", "f": "7,4", "c": "14,4", "kcal": "134,8", "output": OUT(200)},
        {"name": "Блинчики с повидлом со сметаной", "p": "14,4", "f": "11,7", "c": "17,2", "kcal": "229,2", "output": OUT(150 + 20)},
        {"name": "Говядина отварная под белым соусом, каша гречневая вязкая", "p": "28,5", "f": "28,7", "c": "15,0", "kcal": "433,9", "output": OUT(75 + 150)},
        {"name": "Говядина отварная под белым соусом, макароны отварные", "p": "28,9", "f": "28,3", "c": "23,6", "kcal": "466,7", "output": OUT(75 + 150)},
        {"name": "Рагу из свинины (картофель, морковь, лук)", "p": "7,5", "f": "16,5", "c": "12,2", "kcal": "212,9", "output": OUT(75 + 200)},  # было "7,5,"
        {"name": "Фрикадельки паровые (говядина), каша гречневая вязкая", "p": "18,2", "f": "17,5", "c": "22,9", "kcal": "324,0", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина), макароны отварные/соус", "p": "18,6", "f": "17,1", "c": "31,5", "kcal": "356,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Компот"},
        {"name": "Хлеб"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с сыром со сметаной", "p": "1,8", "f": "3,5", "c": "18,6", "kcal": "106,9", "output": OUT(100)},
        {"name": "С-т из помидоров и перца с растит. маслом", "p": "1,4", "f": "3,6", "c": "9,5", "kcal": "69,6", "output": OUT(100)},
        {"name": "С-т «Легкий» (капуста, краб. палочки, огурец, яйцо, зел. горошек) с майонезом", "p": "0,9", "f": "16,5", "c": "2,2", "kcal": "160,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Оладьи картофельные (тёртый картофель, яйцо, лук) со сметаной", "p": "4,0", "f": "9,3", "c": "19,8", "kcal": "179,3", "output": OUT(200 + 20)},
        {"name": "Рулет паровой (говядина, батон, молоко, яйцо), картофельное пюре", "p": "15,4", "f": "19,5", "c": "21,0", "kcal": "324,7", "output": OUT(100 + 150)},
        {"name": "Рыба тушеная в сметане с луком (скумбрия, мука), овсяная каша вязкая", "p": "5,4", "f": "14,7", "c": "16,4", "kcal": "221,9", "output": OUT(100 + 150)},
        {"name": "Рыба тушеная в сметане с луком (скумбрия, мука), картофельное пюре", "p": "5,0", "f": "13,9", "c": "18,9", "kcal": "224,2", "output": OUT(100 + 150)},
        {"name": "Рулет из свинины, фаршированный черносливом, картофельное пюре", "p": "12,9", "f": "38,2", "c": "28,9", "kcal": "518,0", "output": OUT(100 + 150)},  # было 100150
        {"name": "Рулет из свинины, фаршированный черносливом, овсяная каша", "p": "13,3", "f": "39,0", "c": "26,5", "kcal": "515,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кондитерские изделия"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()