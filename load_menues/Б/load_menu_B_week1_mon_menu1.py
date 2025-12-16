from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

# ---------------- НАСТРОЙКИ ----------------
DIET_KIND = "B"          # обычное
CYCLE_NAME = "Меню №1"   # "2" в ваших файлах
DAY_INDEX = 1            # Понедельник
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
    # Dish.output = одно число, поэтому 75/150 -> 225 и т.п.
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # Для диеты B is_diet не трогаем. Для диетических меню позже можно будет "повышать" до True.
    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # Заполняем нутриенты только если они НЕ заполнены (чтобы случайно не перетирать справочник)
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

    # Стираем только этот день (Пн, Меню №1, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Сыр", "p": "16,6", "f": "23,5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "С-т «Солнышко» (горох, лук, морковь, морск. капуста, яйцо) со смет.", "p": "0,5", "f": "5,1", "c": "6,9", "kcal": "74,2", "output": OUT(100)},
        {"name": "Творог с сахаром", "p": "15,4", "f": "8,3", "c": "10,9", "kcal": "180,8", "output": OUT(80)},
        {"name": "Каша молочная гречневая", "p": "3,9", "f": "5,9", "c": "13,9", "kcal": "124,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста цветная с сыром под соусом", "p": "0,4", "f": "0,9", "c": "1,4", "kcal": "15,2", "output": OUT(250)},
        {"name": "Омлет фаршированный мясом (говядина, масло, сметана, мука)", "p": "9,1", "f": "14,5", "c": "2,4", "kcal": "191", "output": OUT(210)},
        {"name": "Свинина тушеная (томат. паста), ячневая каша вязкая", "p": "20,3", "f": "16,4", "c": "15,2", "kcal": "311,5", "output": OUT(75 + 150)},
        {"name": "Свинина тушеная (томат. паста), картофельно-гороховое пюре", "p": "20,2", "f": "16,2", "c": "10,9", "kcal": "292,3", "output": OUT(75 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), ячневая каша вязкая", "p": "12,7", "f": "14,0", "c": "23,3", "kcal": "285,8", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), картофельно-гороховое пюре", "p": "12,6", "f": "13,8", "c": "19,0", "kcal": "266,6", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе растворимый с молоком и сахаром"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т «Лепельская загадка» (куры, морковь, огурец конс., лук, майонез)", "p": "6,0", "f": "27,0", "c": "5,7", "kcal": "292,7", "output": OUT(100)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "1,5", "f": "3,6", "c": "8,4", "kcal": "67,6", "output": OUT(100)},
        {"name": "Салат из моркови, яблок, яиц с растит. маслом", "p": "1,4", "f": "2,6", "c": "3,8", "kcal": "66,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "1,6", "f": "2,6", "c": "5,5", "kcal": "49,7", "output": OUT(300)},
        {"name": "Суп картофельный с рисом (картофель, лук, морковь)", "p": "0,8", "f": "0,8", "c": "6,6", "kcal": "37,7", "output": OUT(300 + 25)},
        {"name": "Суп молочный с овощами (картофель, брокколи, морковь)", "p": "2,0", "f": "1,5", "c": "4,8", "kcal": "40,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Сырники творожные со сметаной (сахар, мука, яйцо)", "p": "14,4", "f": "11,7", "c": "17,2", "kcal": "229,2", "output": OUT(150 + 20)},
        {"name": "Жаркое с говядиной (картофель, лук, томат)", "p": "6,2", "f": "13,0", "c": "15,2", "kcal": "205,2", "output": OUT(75 + 200)},
        {"name": "Кнели паровые из говядины с рисом, макароны отварные", "p": "15,0", "f": "24,3", "c": "12,5", "kcal": "330,3", "output": OUT(140 + 150)},
        {"name": "Кнели паровые из говядины с рисом, каша гречневая рассып./соус", "p": "16,1", "f": "25,1", "c": "31,1", "kcal": "416,3", "output": OUT(140 + 150)},
        {"name": "Птица тушеная в соусе (лук, морковь, томат. паста), каша гречневая рассып.", "p": "16,0", "f": "38,1", "c": "53,9", "kcal": "625,2", "output": OUT(75 + 150)},
        {"name": "Птица тушеная в соусе (лук, морковь, томат. паста), макароны отварные", "p": "16,4", "f": "37,9", "c": "52,9", "kcal": "624,2", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "С-т из помидоров и сладкого перца с растит. маслом", "p": "3,0", "f": "11,7", "c": "15,2", "kcal": "177", "output": OUT(100)},
        {"name": "Салат из моркови с изюмом со сметаной", "p": "1,6", "f": "3,5", "c": "19,7", "kcal": "107,7", "output": OUT(100)},
        {"name": "Винегрет овощной с сельдью (зел. горошек, картофель, морковь, конс. огурец, свекла)", "p": "2,8", "f": "10,2", "c": "8,1", "kcal": "141", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка капустная с яблоками со сметаной", "p": "4,7", "f": "8,6", "c": "9,2", "kcal": "129,6", "output": OUT(200 + 20)},
        {"name": "Рыба жареная (скумбрия, мука), каша перловая вязкая", "p": "19,9", "f": "9,8", "c": "16,8", "kcal": "235,8", "output": OUT(100 + 150)},
        {"name": "Рыба жареная (скумбрия, мука), картофельное пюре", "p": "20,0", "f": "10,3", "c": "17,1", "kcal": "242,5", "output": OUT(100 + 150)},
        {"name": "Бифштекс (говядина, свинина), картофельное пюре", "p": "25,9", "f": "23", "c": "29,4", "kcal": "392,9", "output": OUT(75 + 150)},
        {"name": "Бифштекс (говядина, свинина), каша перловая вязкая", "p": "25,8", "f": "18,1", "c": "31,7", "kcal": "381,5", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), картофельное пюре", "p": "12,2", "f": "14,4", "c": "22,4", "kcal": "293,1", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), каша перловая вязкая", "p": "12,1", "f": "14,4", "c": "22,1", "kcal": "286,4", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Выпечка"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт", "p": "6,2", "f": "5,6", "c": "8,0", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()