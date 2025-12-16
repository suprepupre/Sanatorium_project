import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 5            # Пятница
MARK_DIET = False        # для B не помечаем блюда как диетические


def D(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
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

    # очищаем только этот день (Пт, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Нектар фруктовый", "p": "0.2", "f": "0,0", "c": "10.3", "kcal": "42", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0.2", "c": "17",   "kcal": "34", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "2.8", "f": "1.5", "c": "4.8", "kcal": "44", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Яйцо отварное", "output": None},  # в тексте "1"
        {"name": "Салат «Снегопад» (рис, сыр, лук, яйцо, яблоко) с майонезом", "p": "3.4", "f": "34.3", "c": "1.8", "kcal": "219.8", "output": OUT(100)},
        {"name": "Салат «Агенчик» (морковь, зел. горошек, лук) с растит. маслом", "p": "32.1", "f": "13.5", "c": "6.3", "kcal": "153.6", "output": OUT(100)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Запеканка пшенная с курагой (яйцо, молоко) со сметаной", "p": "1.6", "f": "3.9", "c": "9.5", "kcal": "200,4", "output": OUT(200 + 20)},
        {"name": "Омлет натуральный (яйцо, молоко)", "p": "11.1", "f": "15.2", "c": "5.6", "kcal": "201.5", "output": OUT(200)},
        {"name": "Колбаса по-домашнему, картофельное пюре", "p": "25.1", "f": "63.3", "c": "22.6", "kcal": "458.4", "output": OUT(75 + 150)},
        {"name": "Колбаса по-домашнему, каша пшенная вязкая", "p": "25.9", "f": "63.3", "c": "24.5", "kcal": "433.9", "output": OUT(75 + 150)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, каша пшенная вязкая", "p": "18.3", "f": "7.8", "c": "22.6", "kcal": "323.5", "output": OUT(100 + 150)},
        {"name": "Тефтели (говядина, батон, без яйца) паровые, картофельное пюре", "p": "17.5", "f": "7.8", "c": "20.7", "kcal": "222.3", "output": OUT(100 + 150)},
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
        {"name": "Салат из свеклы с сыром со сметаной", "p": "1.7", "f": "3.5", "c": "16.1", "kcal": "95.6", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты, перца и помидоров с растит. маслом", "p": "1.4", "f": "2.6", "c": "3.8", "kcal": "66.7", "output": OUT(100)},
        {"name": "Салат «Неаполитанский» (куры, картофель, свекла, морковь, огурец марин., майонез)", "p": "1.5", "f": "20.1", "c": "6.9", "kcal": "151.6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "0.8", "f": "2.2", "c": "4.5", "kcal": "41.3", "output": OUT(300)},
        {"name": "Суп картофельный с рыбой (горбуша, томат)", "p": "1.1", "f": "2.4", "c": "7.0", "kcal": "54.7", "output": OUT(300)},
        {"name": "Суп молочный по-могилевски (крахмал, яйцо)", "p": "2.5", "f": "3.1", "c": "9.3", "kcal": "75", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Сырники из творога запеченные (яйцо, мука, сахар, манка) со сметаной", "p": "2.6", "f": "7.0", "c": "21.2", "kcal": "156.3", "output": OUT(150 + 20)},
        {"name": "Плов из свинины (рис, томат. паста)", "p": "29", "f": "31.6", "c": "49.4", "kcal": "35.4", "output": OUT(250)},
        {"name": "Шницель натуральный рубленый (св-гов, яйцо), каша гречневая вязкая", "p": "16.5", "f": "39.1", "c": "21.7", "kcal": "507.3", "output": OUT(75 + 150)},
        {"name": "Шницель натуральный рубленый (св-гов, яйцо), каша рисовая рассыпчатая", "p": "15.8", "f": "35.7", "c": "31.3", "kcal": "541.1", "output": OUT(75 + 150)},
        {"name": "Суфле паровое (куры, мука, яйцо), каша гречневая вязкая", "p": "24.4", "f": "13.8", "c": "18.3", "kcal": "265.2", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (куры, мука, яйцо), каша рисовая рассып./соус", "p": "23.7", "f": "13,6", "c": "27,9", "kcal": "299", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из свежих помидоров со сметаной", "p": "1,5", "f": "3,6", "c": "7,5", "kcal": "63,2", "output": OUT(100)},
        {"name": "Салат «Прибой» (морская капуста, огурец, яблоко, яйцо, майонез)", "p": "6,0", "f": "19,0", "c": "3,3", "kcal": "210,5", "output": OUT(100)},
        {"name": "Салат из свеклы с растит. маслом", "p": "1,4", "f": "5,1", "c": "8,0", "kcal": "81,6", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Запеканка овощная со сметаной (картофель, капуста, морковь, лук, яйцо, манка, мука)", "p": "3,5", "f": "9,6", "c": "10,8", "kcal": "140,8", "output": OUT(200)},
        {"name": "Рыба, запеченная в сметане с луком (скумбрия), картофельно-морковное пюре", "p": "25,2", "f": "13,3", "c": "18,4", "kcal": "215,2", "output": OUT(100 + 200)},
        {"name": "Рыба, запеченная в сметане с луком (скумбрия), каша овсяная вязкая", "p": "5,4", "f": "14,7", "c": "16,5", "kcal": "221,9", "output": OUT(100 + 150)},
        {"name": "Свинина, запеченная с сыром, картофельно-морковное пюре", "p": "19,4", "f": "28,6", "c": "14,6", "kcal": "395,4", "output": OUT(100 + 150)},
        {"name": "Свинина, запеченная с сыром, каша овсяная вязкая", "p": "19,8", "f": "30,3", "c": "12,7", "kcal": "402.1", "output": OUT(100 + 150)},
        {"name": "Голубцы ленивые (говядина, морковь, рис, лук, томат, мука)", "p": "16,3", "f": "25,1", "c": "27,3", "kcal": "403,82", "output": OUT(250)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Выпечка"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Кефир", "p": "6,2", "f": "5,6", "c": "8,0", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()