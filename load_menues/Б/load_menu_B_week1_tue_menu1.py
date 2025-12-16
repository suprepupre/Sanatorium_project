from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

# ---------------- НАСТРОЙКИ ----------------
DIET_KIND = "B"          # обычное
CYCLE_NAME = "Меню №1"   # "2" в ваших файлах
DAY_INDEX = 2            # Вторник
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
    # Dish.output = одно число, поэтому 150/20 -> 170 и т.п.
    return int(total) if total is not None else None


def get_or_create_dish(
    name: str,
    *,
    p=None, f=None, c=None, kcal=None, output=None,
    mark_diet=False
):
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

    # Стираем только этот день (Вт, Меню №1, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        # В документе ккал указано 4,4 (похоже на опечатку), сохраняю как есть:
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "4,4",  "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "С-т из капусты, горошка с яйцом (лук) с растит. маслом", "p": "2,3", "f": "10,1", "c": "5,1", "kcal": "162,6", "output": OUT(100)},
        {"name": "Салат «Особый» (рыбные консервы, зел. горошек, сыр, яйцо, майонез)", "p": "7,1", "f": "17,0", "c": "17,0", "kcal": "257,9", "output": OUT(100)},
        {"name": "Каша молочная рисовая", "p": "4,5", "f": "6,5", "c": "17,8", "kcal": "149,0", "output": OUT(105)},
        {"name": "Яйцо отварное", "p": "10.1", "f": "9.4", "c": "0.6", "kcal": "142.7", "output": None},  # "1шт"
        {"name": "Творог с повидлом", "p": "14,3", "f": "7,7", "c": "11,4", "kcal": "173,8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка из творога и моркови со сметаной (манка, молоко, яйцо)", "p": "12,4", "f": "11,7", "c": "14,3", "kcal": "208,5", "output": OUT(150 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко, без муки)", "p": "9,3", "f": "16,9", "c": "1,7", "kcal": "189,2", "output": OUT(200)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), картофельное пюре", "p": "19,0", "f": "27,2", "c": "13,7", "kcal": "540,9", "output": OUT(75 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), овсяная каша вязкая", "p": "19,4", "f": "28,0", "c": "11,3", "kcal": "538,6", "output": OUT(75 + 150)},  # в тексте 75150
        {"name": "Котлеты паровые (говядина, батон, без яйца), картофельное пюре", "p": "12,2", "f": "14,9", "c": "22,4", "kcal": "293,1", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), овсяная каша вязкая", "p": "12,6", "f": "15,7", "c": "20,0", "kcal": "290,8", "output": OUT(75 + 150)},
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
        {"name": "С-т из свеклы с курагой со сметаной", "p": "1,9", "f": "3,5", "c": "16,5", "kcal": "97,4", "output": OUT(100)},
        {"name": "С-т из белокочанной капусты, огурцов и сладкого перца с растит. маслом", "p": "1,2", "f": "9,1", "c": "23,2", "kcal": "175,9", "output": OUT(100)},
        {"name": "С-т «Павлинка» (куры, сыр, морковь, яблоко, яйцо) с майонезом", "p": "1,5", "f": "20,1", "c": "6,9", "kcal": "157,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ с картофелем и фасолью со сметаной", "p": "0.7", "f": "2.4", "c": "4.5", "kcal": "41.7", "output": OUT(300 + 10)},
        {"name": "Суп картофельный с рыбными фрикадельками (хек, лук)", "p": "15,7", "f": "3,5", "c": "8,2", "kcal": "115,1", "output": OUT(300 + 30)},
        {"name": "Суп молочный с гречневой крупой", "p": "3,0", "f": "3,3", "c": "9,3", "kcal": "78,7", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Вареники ленивые (творог, яйцо, мука) со сметаной", "p": "14,4", "f": "9,8", "c": "13,9", "kcal": "199", "output": OUT(200 + 20)},
        {"name": "Запеканка картофельная с говядиной под соусом", "p": "6,0", "f": "18,2", "c": "16,0", "kcal": "253,1", "output": OUT(250)},
        {"name": "Зразы по-лепельски (куры, свинина, лук, морковь, яйцо, сыр, батон), каша пшенная", "p": "16,5", "f": "33,3", "c": "21,7", "kcal": "466,2", "output": OUT(80 + 150)},
        {"name": "Зразы по-лепельски (куры, свинина, лук, морковь, яйцо, сыр, батон), каша рис рассыпчатая/соус", "p": "16,1", "f": "33,4", "c": "31,0", "kcal": "503,4", "output": OUT(80 + 150)},
        {"name": "Плов из свинины (рис, томат. паста)", "p": "30,7", "f": "51,5", "c": "96", "kcal": "681,1", "output": OUT(250)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат «Белоснежка» (яйцо, белокочанная капуста, огурец) с растит. маслом", "p": "1,4", "f": "7,6", "c": "9,6", "kcal": "110,5", "output": OUT(100)},
        {"name": "С-т «Оливье по-лепельски» (колбаса, картофель, огурец мар., лук, морковь, горошек, яйцо, майонез)", "p": "9,6", "f": "14,4", "c": "6,6", "kcal": "231,5", "output": OUT(100)},
        {"name": "Салат из помидоров со сметаной", "p": "5,0", "f": "8,1", "c": "6,4", "kcal": "114,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная (картофель, морковь, капуста, лук, мука, яйцо) со сметаной", "p": "1,4", "f": "3,6", "c": "16,6", "kcal": "100,4", "output": OUT(200)},
        {"name": "Рыба отварная (скумбрия), картофель тушеный в сметанном соусе", "p": "20,7", "f": "10,9", "c": "15,8", "kcal": "226,8", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (скумбрия), каша гречневая вязкая", "p": "21,5", "f": "5,3", "c": "15,4", "kcal": "194,2", "output": OUT(100 + 150)},
        {"name": "Шницель натуральный отбивной (свинина, сухари), картофель тушеный в сметанном соусе", "p": "27,7", "f": "34,3", "c": "15,4", "kcal": "458,4", "output": OUT(90 + 150)},
        {"name": "Шницель натуральный отбивной (свинина, сухари), каша гречневая вязкая", "p": "28,5", "f": "28,7", "c": "15,0", "kcal": "433,9", "output": OUT(90 + 150)},
        {"name": "Рулет паровой рубленый (говядина, яйцо, батон), картофель тушеный в сметанном соусе", "p": "15,7", "f": "25,4", "c": "23,0", "kcal": "362,2", "output": OUT(100 + 150)},
        {"name": "Рулет паровой рубленый (говядина, яйцо, батон), каша гречневая вязкая", "p": "15.8", "f": "19,8", "c": "22,6", "kcal": "337,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5.6", "f": "6.4", "c": "8.2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5.6", "f": "6.4", "c": "9.5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()