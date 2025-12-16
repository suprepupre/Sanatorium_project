import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 5            # Пятница


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

    if mark_diet and not dish.is_diet:
        dish.is_diet = True

    # не перетираем: заполняем только пустые
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

    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Сок фруктовый без сахара", "p": "0,0", "f": "0,0", "c": "13,0", "kcal": "49,2", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0.0", "f": "0.0", "c": "10.0", "kcal": "41.6", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Яйцо отварное", "output": None},
        {"name": "Салат «Снегопад» (рис, сыр, лук, яйцо, яблоко) с майонезом", "p": "7,34", "f": "19,2", "c": "23,3", "kcal": "300,08", "output": OUT(100)},
        {"name": "Салат «Агенчик» (морковь, зел. горошек, лук) с растит. маслом", "p": "2,5", "f": "12,5", "c": "7,6", "kcal": "205,5", "output": OUT(100)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой (яйцо, молоко) со сметаной", "p": "1.6", "f": "3.9", "c": "9.5", "kcal": "200,4", "output": OUT(200 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "18,0", "f": "29,8", "c": "8,3", "kcal": "402,0", "output": OUT(200)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная вязкая", "p": "19,3", "f": "22", "c": "26,4", "kcal": "310,9", "output": OUT(100 + 150)},
        {"name": "Колбаса по-домашнему, картофельное пюре", "p": "19,8", "f": "18,8", "c": "32,3", "kcal": "412,2", "output": OUT(100 + 150)},
        {"name": "Колбаса по-домашнему, каша пшенная вязкая", "p": "21,5", "f": "23,3", "c": "29", "kcal": "493", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок томатный без сахара"},
        {"name": "Яйцо отварное"},
        {"name": "Сок без сахара"},
        {"name": "Яйцо отварное"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из свеклы с сыром со сметаной", "p": "2,9", "f": "10,0", "c": "5,1", "kcal": "54,8", "output": OUT(100)},
        {"name": "Салат из свежих огурцов, перца и помидоров с растит. маслом", "p": "1,0", "f": "10,70", "c": "13,30", "kcal": "160,40", "output": OUT(100)},
        {"name": "С-т «Неаполитанский» (куры, картофель, свекла, морковь, огурец марин., майонез)", "p": "7,3", "f": "18,4", "c": "20", "kcal": "270,1", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},  # было 300/
        {"name": "Суп картофельный с рыбой (горбуша, томат)", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо)", "p": "8,2", "f": "8,7", "c": "21,0", "kcal": "184,8", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Сырники из творога запеченные (яйцо, мука, без сахара, манка) со сметаной", "p": "2.6", "f": "7.0", "c": "21.1", "kcal": "156.3", "output": OUT(150 + 20)},
        {"name": "Говядина отварная (лук), каша гречневая вязкая", "p": "18,2", "f": "18,5", "c": "22,5", "kcal": "483,6", "output": OUT(75 + 150)},  # было 75//150
        {"name": "Говядина отварная (лук), овощи отварные (капуста, морковь, горошек)", "p": "25,5", "f": "25,3", "c": "27,3", "kcal": "412,3", "output": OUT(75 + 150)},
        {"name": "Шницель натуральный рубленый (св-гов, яйцо), каша гречневая вязкая", "p": "20,2", "f": "20,2", "c": "25,9", "kcal": "445,4", "output": OUT(75 + 150)},
        {"name": "Шницель натуральный рубленый (св-гов, яйцо), овощи отварные", "p": "17,6", "f": "16,3", "c": "13,5", "kcal": "462,2", "output": OUT(75 + 150)},
        {"name": "Суфле паровое (куры, яйцо, мука), каша гречневая вязкая", "p": "17,8", "f": "37,6", "c": "54,6", "kcal": "624", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из помидоров со сметаной", "p": "0,2", "f": "10,7", "c": "5,7", "kcal": "74,2", "output": OUT(100)},
        {"name": "Салат «Прибой» (морская капуста, огурец, яблоко, яйцо, майонез)", "p": "3,0", "f": "17,0", "c": "7,0", "kcal": "197,0", "output": OUT(100)},
        {"name": "Салат из свеклы с растит. маслом", "p": "3,0", "f": "16,1", "c": "3,4", "kcal": "176,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная со сметаной (картофель, капуста, морковь, лук, яйцо, манка, мука)", "p": "3,5", "f": "11,7", "c": "16,75", "kcal": "250,3", "output": OUT(150 + 20)},
        {"name": "Рыба запеченная в сметане с луком (скумбрия), картофельно-морковное пюре", "p": "27,2,", "f": "22,8", "c": "32,5", "kcal": "430", "output": OUT(100 + 150)},
        {"name": "Рыба запеченная в сметане с луком (скумбрия), каша овсяная вязкая", "p": "22,2", "f": "21,6", "c": "21,7", "kcal": "412,6", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, картофельно-морковное пюре", "p": "23,7", "f": "15,4", "c": "21", "kcal": "345,9", "output": OUT(100 + 150)},
        {"name": "Свинина запеченная с сыром, каша овсяная вязкая", "p": "22,5", "f": "30,5", "c": "30,8", "kcal": "499,1", "output": OUT(100 + 150)},
        {"name": "Голубцы ленивые (говядина, морковь, рис, лук, томат, мука)", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,8", "output": OUT(250)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()