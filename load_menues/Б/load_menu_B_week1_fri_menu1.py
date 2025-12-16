from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

# ---------------- НАСТРОЙКИ ----------------
DIET_KIND = "B"          # обычное
CYCLE_NAME = "Меню №1"   # "2" в ваших файлах
DAY_INDEX = 5            # Пятница
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

    # Стираем только этот день (Пт, Меню №1, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",  "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",        "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,4", "f": "0,0", "c": "10,0", "kcal": "40,7", "output": OUT(200)},
    ], is_common=False)

    # В документе у "Йогурт" и "Кефир" в выходе стоит "1" (видимо 1 шт/порция).
    # Чтобы не подставлять неверные граммы, output оставляю None.
    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт", "p": "4,1", "f": "1,5", "c": "5,9", "kcal": "57,0", "output": None},
        {"name": "Салат «Острый» (сыр, морковь, яйцо, чеснок) с майонезом", "p": "10,6", "f": "28,0", "c": "2,6", "kcal": "305,8", "output": OUT(100)},
        {"name": "Каша молочная манная", "p": "2,9", "f": "4,8", "c": "10,9", "kcal": "180,8", "output": OUT(100 + 5)},  # 100/5
        {"name": "Творог со сметаной", "p": "17,1", "f": "12,0", "c": "2,4", "kcal": "185,8", "output": OUT(80)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой со сметаной", "p": "5,3", "f": "7,4", "c": "28,7", "kcal": "176,8", "output": OUT(200 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "9,9", "f": "16,1", "c": "1,8", "kcal": "191,8", "output": OUT(200)},
        {"name": "Птица жареная (сметана), картофельно-гороховое пюре", "p": "20,2", "f": "23,9", "c": "21,5", "kcal": "552,7", "output": OUT(100 + 150)},
        {"name": "Птица жареная (сметана), каша пшенная вязкая", "p": "22,4", "f": "24,7", "c": "19,1", "kcal": "550,4", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), каша пшенная вязкая", "p": "15,3", "f": "20,9", "c": "22,3", "kcal": "340,9", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, молоко), картофельно-гороховое пюре", "p": "15,7", "f": "21,7", "c": "19,9", "kcal": "338,6", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кофе с молоком"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты с огурцом с растит. маслом", "p": "3,6", "f": "9,9", "c": "4,9", "kcal": "123,0", "output": OUT(100)},
        {"name": "Салат из свеклы с сыром со сметаной", "p": "5,0", "f": "8,1", "c": "6,4", "kcal": "114,6", "output": OUT(100)},
        {"name": "Салат «Лепельский» (куры, яйцо, сыр, майонез)", "p": "18,7", "f": "30,1", "c": "2,8", "kcal": "335,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Рассольник (перловка, огурец мар., картофель) со сметаной", "p": "2,3", "f": "2,3", "c": "5,0", "kcal": "49,1", "output": OUT(300 + 10)},
        {"name": "Суп картофельный с горохом", "p": "0,9", "f": "3,4", "c": "3,8", "kcal": "48,0", "output": OUT(300)},
        {"name": "Суп молочный с перловой крупой", "p": "2,0", "f": "2,2", "c": "8,0", "kcal": "59,1", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Котлеты морковные со сметаной (манка, мука, яйцо)", "p": "8,0", "f": "7,4", "c": "51,5", "kcal": "305,7", "output": OUT(150 + 20)},
        {"name": "Говядина отварная под соусом, макароны отварные", "p": "24,4", "f": "25,6", "c": "39,7", "kcal": "555,4", "output": OUT(75 + 150)},
        {"name": "Говядина отварная под соусом, каша гречневая вязкая", "p": "22,8", "f": "32,6", "c": "29,8", "kcal": "468,2", "output": OUT(75 + 150)},
        {"name": "Рулет паровой (говядина, яйцо), макароны отварные/соус", "p": "17,2", "f": "19,9", "c": "30,6", "kcal": "373,0", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, яйцо), овощи отварные (капуста, морковь, горошек)", "p": "16,5", "f": "19,6", "c": "32,2", "kcal": "371,5", "output": OUT(100 + 150)},
        {"name": "Бабка картофельная со свининой (картофель тёртый, лук, чеснок, мука, сметана)", "p": "35.2", "f": "20.8", "c": "11.3", "kcal": "419.3", "output": OUT(250)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с яблоками со сметаной", "p": "1,4", "f": "3,6", "c": "7,7", "kcal": "62,7", "output": OUT(100)},
        {"name": "С-т из белокочанной и морской капусты с растит. маслом", "p": "0,8", "f": "10,1", "c": "3,8", "kcal": "109,8", "output": OUT(100)},
        {"name": "Яйцо, фаршированное сыром (чеснок, майонез)", "p": "8,6", "f": "21,5", "c": "3,7", "kcal": "243,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная со сметаной (капуста, морковь, картофель, лук, манка)", "p": "3,5", "f": "9,6", "c": "10,8", "kcal": "140,8", "output": OUT(200)},
        {"name": "Рыба запеченная в сметане (горбуша, морковь), ячневая каша вязкая", "p": "17,5", "f": "12,8", "c": "19,4", "kcal": "257,1", "output": OUT(100 + 150)},
        {"name": "Рыба запеченная в сметане (горбуша, морковь), картофельное пюре", "p": "17,4", "f": "18,9", "c": "20,5", "kcal": "293,8", "output": OUT(100 + 150)},
        {"name": "Филе из птицы, запечённое с сыром, картофельное пюре", "p": "18,3", "f": "26,8", "c": "24,2", "kcal": "389,1", "output": OUT(90 + 150)},
        # В исходном тексте жиры указаны как "207" — перенёс как есть (207.0).
        {"name": "Филе из птицы, запечённое с сыром, ячневая каша вязкая", "p": "18,4", "f": "207", "c": "23,1", "kcal": "352,4", "output": OUT(90 + 150)},
        {"name": "Тефтели паровые (говядина, батон), картофельное пюре", "p": "15,6", "f": "27,1", "c": "23,3", "kcal": "377,6", "output": OUT(100 + 200)},
        {"name": "Тефтели паровые (говядина, батон), ячневая каша вязкая", "p": "15,7", "f": "21,0", "c": "22,2", "kcal": "340,9", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "output": None},  # в тексте "1", оставляю None
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()