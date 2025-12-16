import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
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

    # нутриенты/выход заполняем только если пусто
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

    # перезаписываем только этот день (Вс, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Творог со сметаной", "p": "3,0", "f": "7,0", "c": "3,4", "kcal": "76,9", "output": OUT(80)},
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0", "kcal": "377", "output": OUT(30)},
        {"name": "Йогурт б/с", "output": None},  # в тексте "1"
        {"name": "Салат из белокочанной капусты и моркови со сметаной", "p": "1,7", "f": "3,5", "c": "16,1", "kcal": "195,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка творожная (яйцо, манка) со сметаной без сахара", "p": "23,7", "f": "19,35", "c": "10,2", "kcal": "325,40", "output": OUT(150 + 20)},
        {"name": "Фрикадельки паровые (говядина, батон), каша пшенная вязкая", "p": "15,5", "f": "17,3", "c": "42,1", "kcal": "463,5", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (минтай), картофельное пюре", "p": "17,3", "f": "9,8", "c": "47,3", "kcal": "493,8", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, картофельное пюре", "p": "39,5", "f": "57,4", "c": "13,3", "kcal": "721", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, каша пшенная вязкая", "p": "40,3", "f": "57,4", "c": "15,2", "kcal": "731,2", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай без сахара"},
        {"name": "Масло"},
    ], is_common=True)

    # 2-ой завтрак — как общая категория внутри завтрака
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок без сахара"},
        {"name": "Вафли на фруктозе"},
        {"name": "Сок томатный"},
        {"name": "Вафли на фруктозе"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "0,6", "f": "10,1", "c": "1,7", "kcal": "99,9", "output": OUT(100)},
        {"name": "Салат из моркови и яблок с яйцом с растит. маслом", "p": "1,1", "f": "20,1", "c": "3,5", "kcal": "101,6", "output": OUT(100)},
        {"name": "Салат мясной по-солигорски (говядина, капуста, рис, лук, майонез)", "p": "6,8", "f": "22,2", "c": "4,4", "kcal": "245,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ с капустой и картофелем (свекла, лук, морковь, картофель) со сметаной", "p": "4,1", "f": "9,2", "c": "16,2", "kcal": "223,6", "output": OUT(300)},
        {"name": "Суп картофельный с фасолью", "p": "5,2", "f": "6,5", "c": "14,3", "kcal": "129,1", "output": OUT(300)},
        {"name": "Затирка с молоком (мука, яйцо)", "p": "9,9", "f": "10,2", "c": "33,3", "kcal": "164,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Фасоль стручковая в яйце (лук)", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,82", "output": OUT(220)},
        {"name": "Жаркое по-домашнему (картофель, свинина, томат)", "p": "1,0", "f": "2,2", "c": "3,5", "kcal": "138,0", "output": OUT(250)},
        {"name": "Котлеты куриные жареные (батон, молоко), овощи отварные (капуста, морковь, горошек)", "p": "27,6", "f": "14,3", "c": "36,3", "kcal": "480,3", "output": OUT(90 + 150)},
        {"name": "Котлеты куриные жареные (батон, молоко), гречневая каша вязкая", "p": "25,6", "f": "11,2", "c": "28,3", "kcal": "421,5", "output": OUT(90 + 150)},  # было 90150
        {"name": "Говядина отварная под соусом, каша перловая рассыпчатая", "p": "27,3", "f": "9,9", "c": "26,5", "kcal": "460,3", "output": OUT(75 + 150)},
        {"name": "Говядина отварная под соусом, каша гречневая вязкая", "p": "26,3", "f": "7,8", "c": "21,2", "kcal": "420,8", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы со сметаной", "p": "0,6", "f": "10,1", "c": "1,7", "kcal": "99,9", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты и огурцов с растит. маслом", "p": "0,8", "f": "9,9", "c": "3,8", "kcal": "108", "output": None},  # 1шт
        {"name": "С-т «Морская фантазия» (краб. палочки, сельдь, морская капуста, морковь, лук, майонез)", "p": "8,2", "f": "20,7", "c": "3,7", "kcal": "237,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты (молоко, мука, яйцо) со сметаной", "p": "9,2", "f": "19", "c": "32,4", "kcal": "340,", "output": OUT(200)},
        {"name": "Рулет паровой (говядина, батон, молоко), картофельно-морковное пюре", "p": "22,3", "f": "40,8", "c": "44,5", "kcal": "636,4", "output": OUT(100 + 150)},
        {"name": "Тефтели рыбные в томатном соусе (минтай), картофельно-морковное пюре", "p": "30,6", "f": "31,3", "c": "42,5", "kcal": "656,9", "output": OUT(100 + 150)},
        {"name": "Тефтели рыбные в томатном соусе (минтай), овсяная каша вязкая", "p": "29,7", "f": "23,9", "c": "27,8", "kcal": "527,1", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, картофельно-морковное пюре", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,82", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, овсяная каша вязкая", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "395", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай без сахара"},
        {"name": "Масло"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()