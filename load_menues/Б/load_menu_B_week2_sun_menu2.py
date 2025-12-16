import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 7            # Воскресенье
MARK_DIET = False        # для B не помечаем блюда как диетические


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # чистим мусор: "44,,0" -> "44..0" -> "44.0", "7,5," -> "7,5"
    s = s.replace(",,", ",").replace("..", ".")
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

    # не перетираем справочник: заполняем только пустые поля
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

    # очищаем только этот день (Вс, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,4", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,4", "c": "4,8",  "kcal": "44,,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Йогурт", "p": "17,1", "f": "12,0", "c": "2,4", "kcal": "185,8", "output": None},  # в тексте "1"
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0,0", "kcal": "108,7", "output": OUT(30)},
        {"name": "Каша молочная «Геркулес»", "p": "3.9", "f": "5.9", "c": "13.9", "kcal": "124.0", "output": OUT(100 + 5)},
        {"name": "Салат «Острый» (сыр, морковь, яйцо, чеснок) с майонезом", "p": "1,9", "f": "5,8", "c": "9,4", "kcal": "90,3", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "14.3", "f": "7.7", "c": "11.4", "kcal": "173.8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с сыром (яйцо, молоко)", "p": "9.1", "f": "14.5", "c": "2.4", "kcal": "191", "output": OUT(240)},
        {"name": "Фрикадельки паровые (говядина, батон), картофельное пюре", "p": "11,7", "f": "11,9", "c": "20,4", "kcal": "265,9", "output": OUT(100 + 150)},
        {"name": "Фрикадельки паровые (говядина, батон), каша пшенная вязкая", "p": "12,5", "f": "11,9", "c": "22,3", "kcal": "270,1", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "20,4", "f": "5,0", "c": "13,8", "kcal": "181,2", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, картофельное пюре", "p": "39,5", "f": "57,4", "c": "13,3", "kcal": "721", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, каша пшенная вязкая", "p": "40,3", "f": "57,4", "c": "15,2", "kcal": "731,2", "output": OUT(100 + 150)},
        {"name": "Сосиски отварные, картофельное пюре", "p": "12.4", "f": "14.2", "c": "20", "kcal": "284", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Сахар"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,8", "f": "3,5", "c": "18,6", "kcal": "106,9", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты и огурца с растит. маслом", "p": "1,5", "f": "9,5", "c": "7,4", "kcal": "121,0", "output": OUT(100)},
        {"name": "Салат «Праздничный» (говядина, лук, морковь, огурец марин.) с майонезом", "p": "8,6", "f": "14,4", "c": "16,0", "kcal": "226,8", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Рассольник (перловка, огурец мар., картофель) со сметаной", "p": "1.1", "f": "2.4", "c": "7.0", "kcal": "54.7", "output": OUT(300 + 10)},
        {"name": "Суп картофельный с фасолью", "p": "2,2", "f": "1,6", "c": "7,8", "kcal": "54,9", "output": OUT(300)},
        {"name": "Затирка с молоком (мука, яйцо)", "p": "3,3", "f": "3,4", "c": "11,1", "kcal": "88,1", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Фасоль стручковая под сырным соусом", "p": "4,5", "f": "6,9", "c": "4,0", "kcal": "104", "output": OUT(220)},
        {"name": "Бабка картофельная со свининой (картофель тёртый, лук, чеснок, мука, сметана)", "p": "9,3", "f": "17,7", "c": "5,5", "kcal": "218,0", "output": OUT(250)},
        {"name": "Биточки по-белорусски (молоко), каша перловая рассыпчатая/соус", "p": "19,3", "f": "22,1", "c": "29,9", "kcal": "399,4", "output": OUT(100 + 150)},
        {"name": "Биточки по-белорусски (молоко), гречневая каша вязкая", "p": "19,3", "f": "22,4", "c": "23,5", "kcal": "375,9", "output": OUT(100 + 150)},  # было 100150
        {"name": "Суфле паровое из курицы, каша перловая рассыпчатая", "p": "21,4", "f": "7,4", "c": "21,9", "kcal": "286,7", "output": OUT(100 + 150)},
        {"name": "Суфле паровое из курицы, гречневая каша вязкая", "p": "16,3", "f": "18,4", "c": "32,9", "kcal": "365,2", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Кисель"},
        {"name": "Хлеб"},
        {"name": "Батон"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свеклы со сметаной", "p": "1,7", "f": "3,5", "c": "8,3", "kcal": "67,0", "output": OUT(100)},
        {"name": "Салат из помидоров, огурцов, перца с растит. маслом", "p": "0,9", "f": "10,2", "c": "3,1", "kcal": "107,9", "output": OUT(100)},
        {"name": "С-т «Изумительный» (краб. палочки, сыр, яйцо, морковь, чеснок, майонез)", "p": "8,3", "f": "21,1", "c": "3,7", "kcal": "241,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Шницель из капусты (молоко, мука, яйцо) со сметаной", "p": "4,0", "f": "11", "c": "10", "kcal": "150", "output": OUT(200)},
        {"name": "Рулет паровой (говядина, батон, молоко), картофельно-морковное пюре", "p": "15,4", "f": "18,9", "c": "20,5", "kcal": "315,7", "output": OUT(100 + 150)},
        {"name": "Тефтели рыбные в томатном соусе (хек), картофельно-морковное пюре", "p": "16,3", "f": "18,4", "c": "32,9", "kcal": "365,2", "output": OUT(100 + 150)},
        {"name": "Тефтели рыбные в томатном соусе (хек), овсяная каша вязкая", "p": "16,7", "f": "19,4", "c": "31,0", "kcal": "371,9", "output": OUT(100 + 150)},
        {"name": "Поджарка из говядины (лук), картофельно-морковное пюре", "p": "22,6", "f": "55,2", "c": "13,2", "kcal": "645,9", "output": OUT(110 + 150)},
        {"name": "Поджарка из говядины (лук), овсяная каша вязкая", "p": "23,0", "f": "56,6", "c": "11,3", "kcal": "652,6", "output": OUT(110 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    print("Готово:", daily_menu)

main()