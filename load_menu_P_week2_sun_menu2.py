import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "P"
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

    # Для П: повышаем is_diet до True (никогда не понижаем)
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

    # перезаписываем только этот день (Вс, Меню №2, П)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Молоко",           "p": "2.8", "f": "1.4", "c": "4.8",  "kcal": "44,0", "output": OUT(200)},
        {"name": "Компот из чернослива без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Каша молочная «Геркулес»", "p": "17,4", "f": "12,2", "c": "2,42", "kcal": "189,64", "output": OUT(100 + 5)},
        {"name": "Йогурт", "p": "3,9", "f": "5,9", "c": "13,9", "kcal": "124,0", "output": None},  # 1шт
        {"name": "Салат из вареной моркови с растит. маслом", "p": "2,2", "f": "3,6", "c": "5,8", "kcal": "63,0", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с сыром (яйцо, молоко)", "p": "9.1", "f": "14.5", "c": "2.4", "kcal": "191", "output": OUT(240)},
        {"name": "Фрикадельки паровые (говядина, батон), картофельное пюре", "p": "18,4", "f": "29,6", "c": "8,8", "kcal": "200,6", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина, батон), каша пшенная вязкая", "p": "16,1", "f": "26", "c": "23,7", "kcal": "395,7", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "17,3", "f": "9,8", "c": "47,3", "kcal": "493,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,5", "f": "3,6", "c": "7,5", "kcal": "63,2", "output": OUT(100)},
        {"name": "Рыба отварная (филе), овощной гарнир", "p": "12,1", "f": "9,10", "c": "3,90", "kcal": "122,6", "output": OUT(50 + 50)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный «Геркулес»", "p": "5,2", "f": "6,5", "c": "14,3", "kcal": "109,1", "output": OUT(300)},
        {"name": "Затирка с молоком (мука, яйцо)", "p": "4,9", "f": "10,2", "c": "23,3", "kcal": "114,3", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Фасоль стручковая под сырным соусом", "p": "1,0", "f": "2,2", "c": "3,5", "kcal": "138,0", "output": OUT(150)},
        {"name": "Птица отварная, каша гречневая вязкая", "p": "27,6", "f": "14,3", "c": "36,3", "kcal": "480,3", "output": OUT(100 + 150)},
        {"name": "Птица отварная, каша перловая рассыпчатая", "p": "25,6", "f": "11,2", "c": "28,3", "kcal": "421,5", "output": OUT(100 + 150)},
        {"name": "Суфле паровое из курицы, каша перловая рассыпчатая", "p": "21.4", "f": "7.4", "c": "21.9", "kcal": "286.7", "output": OUT(100 + 150)},
        {"name": "Суфле паровое из курицы, каша гречневая вязкая", "p": "16.3", "f": "18.4", "c": "32.9", "kcal": "365.2", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы со сметаной", "p": "1,9", "f": "5,2", "c": "4,6", "kcal": "55,5", "output": OUT(100)},
        {"name": "Яйцо рубленое со сметаной", "p": "1,6", "f": "3,5", "c": "7,7", "kcal": "63,7", "output": OUT(70)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты (молоко, мука, яйцо) со сметаной", "p": "9,2", "f": "19", "c": "32,4", "kcal": "340,", "output": OUT(220 + 20)},
        {"name": "Рулет паровой (говядина, батон, молоко), каша овсяная", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,82", "output": OUT(100 + 150)},
        {"name": "Рулет паровой (говядина, батон, молоко), картофельно-морковное пюре", "p": "22,3", "f": "40,8", "c": "44,5", "kcal": "636,4", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (хек), каша овсяная", "p": "22.6", "f": "40.3", "c": "31", "kcal": "276.3", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (хек), картофельно-морковное пюре", "p": "23.1", "f": "41", "c": "32.8", "kcal": "288.4", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай"},
        {"name": "Сахар"},
        {"name": "Кондитерские изделия"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()