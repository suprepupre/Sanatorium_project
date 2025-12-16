import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3" в ваших файлах
DAY_INDEX = 2            # Вторник
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

    # очищаем только этот день (Вт, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Сок фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "41,4", "output": OUT(200)},
        {"name": "Сок томатный",  "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Молоко",        "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной и морской капусты с растит. маслом", "p": "1,2", "f": "5,2", "c": "11,0", "kcal": "94,1", "output": OUT(100)},
        {"name": "Салат «Чайка» (сыр, яйцо, зел. горошек, лук, майонез)", "p": "11.2", "f": "25.4", "c": "2.6", "kcal": "289.5", "output": OUT(100)},
        {"name": "Сыр", "p": "16.6", "f": "23.5", "c": "0", "kcal": "326", "output": OUT(30)},
        {"name": "Яйцо отварное", "output": None},  # в тексте "1" (шт)
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с колбасой вареной (яйцо, молоко, масло)", "p": "16,5", "f": "12,9", "c": "12,5", "kcal": "229,6", "output": OUT(200)},
        {"name": "Морковь припущенная в молочном соусе (мука, молоко)", "p": "1,8", "f": "4,9", "c": "9,6", "kcal": "86,8", "output": OUT(200)},
        {"name": "Биточки паровые (говядина, батон, без яйца), каша ячневая вязкая", "p": "12,7", "f": "13,5", "c": "23,3", "kcal": "285,8", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца), картофельно-гороховое пюре", "p": "17,0", "f": "16,7", "c": "27,3", "kcal": "333,3", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, каша ячневая вязкая", "p": "24,2", "f": "47,9", "c": "21,4", "kcal": "617,5", "output": OUT(75 + 150)},
        {"name": "Печень (куриная) жареная с луком, картофельно-гороховое пюре", "p": "34,8", "f": "48,6", "c": "25,4", "kcal": "665,0", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Винегрет овощной с сельдью (зел. горошек, картофель, морковь, конс. огурец, свекла)", "p": "5,0", "f": "8,1", "c": "6,4", "kcal": "114,6", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров со сметаной", "p": "1,4", "f": "7,6", "c": "6,2", "kcal": "97,4", "output": OUT(100)},
        {"name": "С-т «Оливье по-лепельски» (колбаса, картофель, огурец мар., лук, морковь, горошек, яйцо, майонез)", "p": "6,0", "f": "27,0", "c": "5,7", "kcal": "292,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "15,7", "f": "3,5", "c": "8,2", "kcal": "115,4", "output": OUT(300)},
        {"name": "Суп картофельный с рыбными фрикадельками (хек, лук, яйцо)", "p": "0,9", "f": "3,4", "c": "3,8", "kcal": "48,0", "output": OUT(300 + 30)},
        {"name": "Суп молочный овсяный с хлопьями «Геркулес»", "p": "2,6", "f": "3,4", "c": "7,3", "kcal": "70,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста цветная под молочным соусом", "p": "4,0", "f": "10,7", "c": "10,1", "kcal": "149,5", "output": OUT(250)},
        {"name": "Зразы рубленые запеченные (говядина, батон, молоко, яйцо), каша рисовая вязкая", "p": "17,0", "f": "34,4", "c": "36,9", "kcal": "515,1", "output": OUT(100 + 150)},  # было 100150
        {"name": "Зразы рубленые запеченные (говядина, батон, молоко, яйцо), гречневая каша рассыпчатая", "p": "17,7", "f": "34,4", "c": "36,9", "kcal": "514,5", "output": OUT(100 + 150)},
        {"name": "Жаркое с говядиной (картофель, лук, томат)", "p": "17,0", "f": "34,4", "c": "36,9", "kcal": "515,1", "output": OUT(75 + 200)},
        {"name": "Суфле паровое (курица, яйцо), каша рисовая вязкая", "p": "20,8", "f": "11,9", "c": "28,8", "kcal": "450,3", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (курица, яйцо), гречневая каша рассыпчатая", "p": "21,5", "f": "11,9", "c": "28,8", "kcal": "449,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из помидоров с растит. маслом", "p": "1,5", "f": "9,5", "c": "7,4", "kcal": "121,0", "output": OUT(100)},
        {"name": "С-т из печени (печень говяжья, картофель, огурец, морковь) с майонезом", "p": "4,0", "f": "12,7", "c": "3,6", "kcal": "144,1", "output": OUT(100)},
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,4", "f": "3,6", "c": "9,8", "kcal": "71,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Блинчики с повидлом со сметаной", "p": "7,4", "f": "10,1", "c": "43,2", "kcal": "289,8", "output": OUT(135 + 20)},
        {"name": "Рыба, запеченная в сметане с луком (скумбрия), овсяная каша вязкая", "p": "20,8", "f": "26,2", "c": "15,9", "kcal": "297,6", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в сметане с луком (скумбрия), картофельное пюре", "p": "20,4", "f": "25,4", "c": "18,3", "kcal": "386,0", "output": OUT(100 + 150)},
        {"name": "Шницель натуральный отбивной (свинина, сухари, яйцо), картофельное пюре", "p": "13,4", "f": "16,4", "c": "21,5", "kcal": "347,2", "output": OUT(90 + 150)},  # было 90150
        {"name": "Шницель натуральный отбивной (свинина, сухари, яйцо), овсяная каша вязкая", "p": "11,9", "f": "18.3", "c": "26,5", "kcal": "336,1", "output": OUT(90 + 150)},
        {"name": "Тефтели паровые (говядина, батон, молоко, без яйца), картофельное пюре", "p": "15,3", "f": "22,2", "c": "21,3", "kcal": "340,1", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые (говядина, батон, молоко, без яйца), овсяная каша вязкая", "p": "15,7", "f": "22,0", "c": "18,9", "kcal": "337,8", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Выпечка"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()