from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

# ---------------- НАСТРОЙКИ ----------------
DIET_KIND = "B"          # обычное
CYCLE_NAME = "Меню №1"   # "2" в ваших файлах
DAY_INDEX = 6            # Суббота
MARK_DIET = False        # для диеты B НЕ помечаем блюда как диетические
# ------------------------------------------


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    return Decimal(s.replace(",", "."))


def OUT(total):
    # Dish.output = одно число, поэтому 100/5 -> 105, 200/20 -> 220 и т.п.
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, _created = Dish.objects.get_or_create(name=name)

    # Для диеты B is_diet не трогаем. Для диетических меню позже можно будет "повышать" до True.
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # Заполняем нутриенты только если в справочнике пусто (не перетираем)
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

    # Стираем только этот день (Сб, Меню №1, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,2", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,0", "c": "6,5", "kcal": "24,5", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог с повидлом", "p": "14,3", "f": "7,7", "c": "11,4", "kcal": "113,8", "output": OUT(80)},
        {"name": "Салат из белокочанной капусты, свежего огурца и зел. горошка с растит. маслом", "p": "1,2", "f": "5,2", "c": "11,0", "kcal": "94,1", "output": OUT(100)},
        {"name": "Салат из кукурузы с черносливом (кукуруза, сыр, чернослив, чеснок) с майонезом", "p": "8,3", "f": "23,9", "c": "1,6", "kcal": "254,1", "output": OUT(100)},
        {"name": "Каша молочная гречневая", "p": "3,9", "f": "5,9", "c": "13,9", "kcal": "124,0", "output": OUT(100 + 5)},  # 100/5
        # В исходнике "116.6" — перенёс как есть.
        {"name": "Сыр", "p": "116.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста брокколи, запеченная с сыром под соусом (мука, сыр, молоко)", "p": "7,8", "f": "15,4", "c": "16,8", "kcal": "238,6", "output": OUT(200)},
        {"name": "Свинина по-домашнему (мука, сметана), картофельное пюре", "p": "25,1", "f": "63,3", "c": "22,6", "kcal": "440.7", "output": OUT(75 + 150)},
        {"name": "Свинина по-домашнему (мука, сметана), каша овсяная вязкая", "p": "25,9", "f": "63,3", "c": "24,5", "kcal": "453.8", "output": OUT(75 + 150)},  # 75150
        {"name": "Птица отварная, картофельное пюре", "p": "19,9", "f": "16,6", "c": "14,3", "kcal": "310,7", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша овсяная вязкая", "p": "20,7", "f": "16,6", "c": "16,2", "kcal": "320,9", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон, масло), каша овсяная вязкая", "p": "10,2", "f": "10,9", "c": "9,4", "kcal": "133,8", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, картофельное пюре", "p": "12,4", "f": "14,2", "c": "20", "kcal": "284", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Сахар"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т из огурцов и помидоров с растит. маслом", "p": "2,3", "f": "10,1", "c": "5,1", "kcal": "162,6", "output": OUT(100)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "2,1", "f": "3,5", "c": "14,7", "kcal": "93,0", "output": OUT(100)},
        {"name": "С-т «Павлинка» (куры, сыр, морковь, яблоко, яйцо) с майонезом", "p": "14", "f": "24,6", "c": "3,5", "kcal": "288,5", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп из овощей (брокколи, морковь, картофель, стручковая фасоль)", "p": "0,8", "f": "2,2", "c": "4,5", "kcal": "41,3", "output": OUT(300)},
        {"name": "Борщ сибирский (фасоль, лук, томат) со сметаной", "p": "0,7", "f": "0,9", "c": "5,2", "kcal": "31,8", "output": OUT(300 + 30)},
        {"name": "Суп молочный с макаронами", "p": "2,9", "f": "3,2", "c": "9,7", "kcal": "79,5", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Зразы творожные (яйцо, мука, курага) со сметаной", "p": "13,7", "f": "12,7", "c": "31,6", "kcal": "290,9", "output": OUT(150 + 20)},
        {"name": "Печень (куриная) жареная с луком, каша рисовая рассыпчатая", "p": "30,8", "f": "23,1", "c": "36,2", "kcal": "476,9", "output": OUT(75 + 150)},
        {"name": "Печень (куриная) жареная с луком, перловая каша вязкая", "p": "30,3", "f": "22,5", "c": "24,7", "kcal": "422,8", "output": OUT(75 + 150)},
        {"name": "Плов из свинины (рис, томат. паста)", "p": "26,0", "f": "50,8", "c": "42,0", "kcal": "740,5", "output": OUT(250)},
        {"name": "Говядина тушеная с черносливом (морковь, лук, томат), каша рисовая рассыпчатая", "p": "16,1", "f": "33,4", "c": "31,0", "kcal": "483,4", "output": OUT(75 + 150)},
        {"name": "Говядина тушеная с черносливом (морковь, лук, томат), перловая каша вязкая", "p": "15,6", "f": "32,8", "c": "19,5", "kcal": "429,3", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из огурцов с растит. маслом", "p": "1,7", "f": "3,5", "c": "8,3", "kcal": "67,0", "output": OUT(100)},
        {"name": "С-т «Красная шапочка» (свекла, сыр, помидор, чеснок) с майонезом", "p": "4,3", "f": "20,7", "c": "18,5", "kcal": "283,1", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, яблок и моркови со сметаной", "p": "1,3", "f": "8,1", "c": "5,0", "kcal": "96,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты со сметаной (молоко, мука, яйцо)", "p": "4,0", "f": "10,7", "c": "10,1", "kcal": "149,", "output": OUT(200 + 20)},
        {"name": "Блинчики с творогом со сметаной", "p": "3,6", "f": "24,8", "c": "25,6", "kcal": "185", "output": OUT(135 + 20)},
        {"name": "Рыба, запеченная в майонезе (скумбрия, лук), гречневая каша вязкая", "p": "21,5", "f": "25,5", "c": "29,5", "kcal": "432,8", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в майонезе (скумбрия, лук), картофельно-морковное пюре", "p": "20,4", "f": "24,8", "c": "17,8", "kcal": "377,0", "output": OUT(100 + 150)},
        {"name": "Свинина отбивная по-лепельски (сыр, чеснок, лук, морковь), каша гречневая вязкая", "p": "20,1", "f": "34,1", "c": "24,6", "kcal": "440,3", "output": OUT(100 + 150)},
        {"name": "Свинина отбивная по-лепельски (сыр, чеснок, лук, морковь), картофельно-морковное пюре", "p": "19,0", "f": "33,4", "c": "12,9", "kcal": "384,5", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), гречневая каша вязкая", "p": "16,4", "f": "21,3", "c": "32,5", "kcal": "386,9", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки, лук), картофельно-морковное пюре", "p": "15,3", "f": "20,6", "c": "20,8", "kcal": "331,1", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()