import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
DAY_INDEX = 4            # Четверг


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

    # перезаписываем только этот день (Чт, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из кураги без сахара", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "19,32", "f": "13,56", "c": "2,71", "kcal": "209,9", "output": OUT(80)},
        {"name": "Салат из белокочанной капусты и свежего огурца с растит. маслом", "p": "6,0", "f": "19,0", "c": "3,3", "kcal": "210,5", "output": OUT(100)},
        {"name": "Каша молочная пшенная", "p": "4,10", "f": "5,40", "c": "21,40", "kcal": "151,8", "output": OUT(100 + 5)},
        {"name": "Салат «Чайка» (сыр, яйцо, зел. горошек, лук, майонез)", "p": "11.2", "f": "25.4", "c": "2.6", "kcal": "289.5", "output": OUT(100)},
        {"name": "Икра кабачковая консервированная", "p": "0,0", "f": "7,7", "c": "7,0", "kcal": "97,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка творожная без сахара (яйцо, творог, манка) со сметаной", "p": "16,5", "f": "12,9", "c": "12,5", "kcal": "229,6", "output": OUT(150 + 20)},
        {"name": "Омлет драчена (мука)", "p": "11,1", "f": "15,2", "c": "5,6", "kcal": "201,5", "output": OUT(210)},
        {"name": "Свинина тушеная (томат, мука), капуста тушеная", "p": "23,7", "f": "48,7", "c": "20,2", "kcal": "621,3", "output": OUT(75 + 150)},
        {"name": "Свинина тушеная (томат, мука), каша овсяная вязкая", "p": "24,1", "f": "49,5", "c": "17,8", "kcal": "619,0", "output": OUT(75 + 150)},
        {"name": "Тефтели с рисом в сметанном соусе (говядина, лук, молоко), каша овсяная вязкая", "p": "16,7", "f": "39,3", "c": "31,2", "kcal": "538,1", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # 2-ой завтрак (12:00) — в системе нет отдельного приёма пищи, добавляем как общие позиции
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок томатный"},
        {"name": "Яйцо отварное"},
        {"name": "Сок без сахара"},
        {"name": "Яйцо отварное"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат «Бурячок» (свекла, лук, горошек, яблоко) с растит. маслом", "p": "1,5", "f": "9,1", "c": "7,5", "kcal": "117,8", "output": OUT(100)},
        {"name": "Салат из огурцов со сметаной", "p": "1.6", "f": "3.5", "c": "19.", "kcal": "107.7", "output": OUT(100)},
        {"name": "С-т «Гродненский» (говядина, б/к капуста, помидор, лук) с майонезом", "p": "9,8", "f": "14,4", "c": "17,2", "kcal": "236,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ белорусский (свекла, картофель, томат) со сметаной", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "53,2", "output": OUT(300)},
        {"name": "Суп картофельный с рыбой (горбуша)", "p": "1,0", "f": "0,8", "c": "7,5", "kcal": "42,5", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо, молоко)", "p": "2,0", "f": "1,5", "c": "11,8", "kcal": "40,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Говядина отварная, каша гречневая вязкая", "p": "9,2", "f": "22,8", "c": "18", "kcal": "523.3", "output": OUT(75 + 150)},
        {"name": "Говядина отварная, овощи отварные (капуста, морковь, горошек)", "p": "9.2", "f": "22.8", "c": "18", "kcal": "523.3", "output": OUT(75 + 150)},
        {"name": "Суфле паровое (курица, рис, мука, молоко, яйцо), овощи отварные (капуста, морковь, горошек)", "p": "22.4", "f": "10.3", "c": "29.7", "kcal": "468.8", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (курица, яйцо), каша гречневая вязкая", "p": "23.5", "f": "12.8", "c": "29.2", "kcal": "471.3", "output": OUT(100 + 150)},
        {"name": "Печень жареная (говядина) с луком, каша гречневая вязкая", "p": "42,1", "f": "25,4", "c": "110,8", "kcal": "844,5", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из помидоров с растит. маслом", "p": "2,8", "f": "8,7", "c": "3,8", "kcal": "103,9", "output": OUT(100)},
        {"name": "С-т из кукурузы с крабовыми палочками (лук, огурец конс., яйцо, рис) с майонезом", "p": "3,9", "f": "16,5", "c": "10,9", "kcal": "206,6", "output": OUT(100)},
        {"name": "Салат из свеклы с курагой со сметаной", "p": "1,50", "f": "4,70", "c": "7,30", "kcal": "71,40", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Капуста цветная под молочным соусом (мука, молоко)", "p": "4,7", "f": "8,6", "c": "9,2", "kcal": "129,6", "output": OUT(250)},
        {"name": "Рыба, запеченная в майонезе (скумбрия, лук, мука), каша пшеничная вязкая", "p": "21,2", "f": "5,0", "c": "15,7", "kcal": "191,4", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в майонезе (скумбрия, лук, мука), картофельно-морковное пюре", "p": "26,3", "f": "10,0", "c": "24,8", "kcal": "280,3", "output": OUT(100 + 150)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), пшеничная каша", "p": "22.2", "f": "25.7", "c": "15.2", "kcal": "485.2", "output": OUT(75 + 150)},
        {"name": "Птица тушеная в соусе (мука, томат, лук, морковь), картофельно-морковное пюре", "p": "21.4", "f": "29.4", "c": "15.3", "kcal": "475", "output": OUT(75 + 150)},
        {"name": "Фрикадельки паровые (говядина без яйца, батон), картофельно-морковное пюре", "p": "21,2", "f": "25,7", "c": "22,9", "kcal": "389,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()