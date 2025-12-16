import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 3            # Среда


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    # чистим мусор: "10," -> "10", "75//150" обрабатываем отдельно, тут только числа
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
        # общие позиции (хлеб/чай/батон/масло) не помечаем как diet=True
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

    # перезаписываем только этот день (Ср, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок фруктовый без сахара", "p": "0,0", "f": "0,2", "c": "10,", "kcal": "38,0", "output": OUT(200)},
        {"name": "Сок томатный",             "p": "0,8", "f": "0,0", "c": "20,", "kcal": "81",   "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,8", "f": "0,0", "c": "20,", "kcal": "81", "output": OUT(200)},
        {"name": "Молоко",                  "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116",  "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты, лука, сладкого перца с растит. маслом", "p": "10,4", "f": "12,3", "c": "12,5", "kcal": "227,5", "output": OUT(100)},
        {"name": "Салат «Скорый» (варёная колбаса, огурец мар., морковь, лук, томат) с майонезом", "p": "1,0", "f": "10,2", "c": "3,5", "kcal": "110", "output": OUT(100)},
        {"name": "Каша пшенная молочная", "p": "4,30", "f": "6,20", "c": "16,4", "kcal": "138", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "19,3", "f": "13,5", "c": "2,71", "kcal": "210", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с сыром (молоко, яйцо, сыр)", "p": "18,60", "f": "33,80", "c": "3,40", "kcal": "378,40", "output": OUT(200)},
        {"name": "Свинина по-деревенски (сметана, лук), капуста тушеная", "p": "23,2", "f": "52,1", "c": "0,6", "kcal": "499", "output": OUT(75 + 150)},  # 75//150
        {"name": "Свинина по-деревенски (сметана, лук), каша овсяная вязкая", "p": "23.2", "f": "52.2", "c": "0.6", "kcal": "499", "output": OUT(75 + 150)},
        # "100/1500" трактуем как 100/150
        {"name": "Сосиски отварные, каша овсяная вязкая", "p": "12,1", "f": "0,0", "c": "1,4", "kcal": "233,6", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон), каша овсяная вязкая", "p": "16,5", "f": "22,8", "c": "34", "kcal": "409,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
    ], is_common=True)

    # 2-ой завтрак (в системе нет отдельного приёма пищи) — добавим как общее
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Йогурт б/с"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из помидоров и сладкого перца с растит. маслом", "p": "1,5", "f": "3,6", "c": "2,9", "kcal": "155,2", "output": OUT(100)},
        {"name": "Салат «Смак» (куры, рис, яйцо, сыр, курага, майонез)", "p": "2,30", "f": "27,10", "c": "3,70", "kcal": "154,40", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ сибирский (фасоль, лук, томат) со сметаной", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "33,2", "output": OUT(300)},
        {"name": "Суп картофельный с рисом (картофель, лук, морковь)", "p": "6,3", "f": "5,4", "c": "23,7", "kcal": "170,4", "output": OUT(300)},
        {"name": "Суп молочный с овощами (морковь, картофель, стручк. фасоль, капуста, без муки)", "p": "6,6", "f": "4,8", "c": "21,3", "kcal": "150,9", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "23,8", "f": "32,4", "c": "41,4", "kcal": "236,7", "output": OUT(200)},
        {"name": "Котлеты «Оригинальные» (куры, морковь, сухари), овощи отварные", "p": "15,6", "f": "47,3", "c": "41,6", "kcal": "458,0", "output": OUT(100 + 150)},
        {"name": "Котлеты «Оригинальные» (куры, морковь, сухари), каша пшеничная", "p": "23,3", "f": "12,8", "c": "59,8", "kcal": "448,8", "output": OUT(100 + 150)},
        {"name": "Говядина отварная под белым соусом, овощи отварные (капуста, морковь, горошек)", "p": "36,9", "f": "15,7", "c": "31,6", "kcal": "427,3", "output": OUT(75 + 150)},
        {"name": "Говядина отварная под белым соусом, каша пшеничная", "p": "33,8", "f": "15,7", "c": "12,6", "kcal": "319,7", "output": OUT(75 + 150)},
        {"name": "Печень (говяжья) жареная с луком, каша пшеничная", "p": "32,9", "f": "21,4", "c": "40,1", "kcal": "454,5", "output": OUT(75 + 150)},
        {"name": "Печень (говяжья) жареная с луком, овощи отварные (капуста, морковь, горошек)", "p": "27,8", "f": "17", "c": "26", "kcal": "381,4", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "С-т «Русалочка» (горошек, краб. палочки, огурец, морская капуста, яйцо, лук) с майонезом", "p": "0,8", "f": "10,1", "c": "3,8", "kcal": "103,8", "output": OUT(100)},
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,6", "f": "3,5", "c": "14,7", "kcal": "91,6", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров с растит. маслом", "p": "1,3", "f": "5,1", "c": "8,8", "kcal": "108", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "9,2", "f": "26,2", "c": "21,3", "kcal": "456,", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), перловая каша вязкая", "p": "19,3", "f": "22,8", "c": "16,4", "kcal": "311", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки), перловая каша", "p": "21", "f": "59,9", "c": "15,5", "kcal": "575", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца, без муки), картофельное пюре", "p": "20.3", "f": "25,3", "c": "36,9", "kcal": "462", "output": OUT(100 + 150)},
        {"name": "Филе из птицы, запеченное с сыром, перловая каша вязкая", "p": "13,4", "f": "40,3", "c": "32,7", "kcal": "351,9", "output": OUT(100 + 150)},
        {"name": "Филе из птицы, запеченное с сыром, картофельное пюре", "p": "16,1", "f": "49,0", "c": "16,2", "kcal": "365,3", "output": OUT(100 + 150)},
        {"name": "Капуста брокколи с сыром под соусом", "p": "3,4", "f": "6,9", "c": "7,7", "kcal": "106,7", "output": OUT(250)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт б/с", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=True)

    print("Готово:", daily_menu)

main()