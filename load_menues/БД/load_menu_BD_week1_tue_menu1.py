import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №1"   # "2"
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


def OUT(total):
    return int(total) if total is not None else None


def get_or_create_dish(name: str, *, p=None, f=None, c=None, kcal=None, output=None, mark_diet=False):
    dish, created = Dish.objects.get_or_create(name=name)

    # для БД повышаем is_diet до True (никогда не понижаем)
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
        # общие позиции (хлеб/чай/батон/масло) не помечаем как diet
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

    # перезаписываем только этот день (Вт, Меню №1, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Сок фруктовый без сахара", "p": "0,8", "f": "0,0", "c": "20,0", "kcal": "81,4", "output": OUT(200)},
        {"name": "Молоко", "p": "2,8", "f": "1,5", "c": "4,8", "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "С-т из капусты, горошка с яйцом (лук) с растит. маслом", "p": "2,3", "f": "10,1", "c": "5,1", "kcal": "162,6", "output": OUT(100)},
        {"name": "Абрикос сушеный (курага)", "output": OUT(30)},  # БЖУ не указаны
        {"name": "Яйцо отварное", "p": "1,9", "f": "18,1", "c": "4,5", "kcal": "187,3", "output": None},  # в тексте "1"
        {"name": "Творог со сметаной", "p": "7,11", "f": "9,15", "c": "0,00", "kcal": "113,10", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка из творога и моркови со сметаной (манка, яйцо, без сахара)", "p": "12.4", "f": "11.7", "c": "14,3", "kcal": "208,5", "output": OUT(150 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко, без муки)", "p": "9,3", "f": "16.9", "c": "1,7", "kcal": "189,2", "output": OUT(200)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), картофельное пюре", "p": "19,0", "f": "27,2", "c": "13,7", "kcal": "540,9", "output": OUT(75 + 150)},
        {"name": "Бифштекс «Морской» (скумбрия, свинина, яйцо), овсяная каша", "p": "19,4", "f": "28,0", "c": "11,3", "kcal": "538,6", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), овсяная каша вязкая", "p": "12,2", "f": "14,9", "c": "22,4", "kcal": "293,1", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, без яйца), картофельное пюре", "p": "12,6", "f": "15,7", "c": "20,0", "kcal": "290,8", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # 2-ой завтрак / полдник (snack) пропускаем

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "С-т из свеклы с курагой со сметаной", "p": "1,9", "f": "3,5", "c": "16,5", "kcal": "97,4", "output": OUT(100)},
        {"name": "С-т из белокочанной капусты, огурца и сладкого перца с растит. маслом", "p": "1,2", "f": "9,1", "c": "23,2", "kcal": "175,9", "output": OUT(100)},
        {"name": "С-т «Павлинка» (куры, сыр, морковь, яблоко, яйцо) с майонезом", "p": "1,5", "f": "20,1", "c": "6,9", "kcal": "157,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ с картофелем и фасолью со сметаной", "p": "0.7", "f": "2.4", "c": "4.5", "kcal": "41.7", "output": OUT(300 + 10)},
        {"name": "Суп картофельный с рыбными фрикадельками (хек, лук)", "p": "15,7", "f": "3,5", "c": "8,2", "kcal": "115,1", "output": OUT(300 + 30)},
        {"name": "Суп молочный с гречневой крупой", "p": "3,0", "f": "3,3", "c": "9,3", "kcal": "78,7", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Вареники ленивые (творог, яйцо, мука) со сметаной", "p": "14.4", "f": "9,8", "c": "13,9", "kcal": "199", "output": OUT(200 + 20)},
        {"name": "Запеканка картофельная с говядиной под соусом", "p": "6,0", "f": "18,2", "c": "16,0", "kcal": "253,1", "output": OUT(250)},
        {"name": "Зразы по-лепельски (куры, свинина, лук, морковь, яйцо, сыр, батон), каша пшенная", "p": "16,5", "f": "33,3", "c": "21,7", "kcal": "466,2", "output": OUT(80 + 150)},
        {"name": "Говядина отварная под соусом, каша пшенная", "p": "24", "f": "54,3", "c": "19,9", "kcal": "428,6", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат «Белоснежка» (яйцо, б/к капуста, огурец) с растит. маслом", "p": "1,4", "f": "7,6", "c": "9,6", "kcal": "110,5", "output": OUT(100)},
        {"name": "С-т «Оливье по-лепельски» (колбаса, картофель, огурец мар., лук, морковь, горошек, яйцо, майонез)", "p": "9,6", "f": "14,4", "c": "6,6", "kcal": "231,5", "output": OUT(100)},
        {"name": "Салат из помидоров со сметаной", "p": "5,0", "f": "8,1", "c": "6,4", "kcal": "114,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная (картофель, морковь, капуста, лук, мука, яйцо) со сметаной", "p": "1,4", "f": "3,6", "c": "16,6", "kcal": "100,4", "output": OUT(200)},
        # У следующих блюд выход в тексте “съехал” (стоят числа 20,7/21,5/27,7/28,5),
        # поэтому output оставляю None, чтобы не записать неверные граммы.
        {"name": "Рыба отварная (скумбрия), картофель тушеный в сметанном соусе", "p": "20,7", "f": "10,9", "c": "15,8", "kcal": "226,8", "output": None},
        {"name": "Рыба отварная (скумбрия), каша гречневая вязкая", "p": "21,5", "f": "5,3", "c": "15,4", "kcal": "194,2", "output": None},
        {"name": "Шницель натуральный отбивной (свинина, сухари), картофель тушеный в сметанном соусе", "p": "27,7", "f": "34,3", "c": "15,4", "kcal": "458,4", "output": None},
        {"name": "Шницель натуральный отбивной (свинина, сухари), каша гречневая вязкая", "p": "28,5", "f": "28,7", "c": "15,0", "kcal": "433,9", "output": None},
        {"name": "Рулет паровой рубленый (говядина, яйцо, батон), каша гречневая вязкая", "p": "15,8", "f": "19,8", "c": "22,6", "kcal": "337,7", "output": OUT(100 + 150)},
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