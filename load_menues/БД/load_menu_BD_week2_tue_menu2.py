import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
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
        mark_diet = (not is_common)  # общие (хлеб/чай/батон/масло) не помечаем как diet

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

    # перезаписываем только этот день (Вт, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из чернослива без сахара", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0.8", "f": "0.0", "c": "20", "kcal": "81", "output": OUT(200)},
        {"name": "Сок фруктовый без сахара", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной и морской капусты с растит. маслом", "p": "1,2", "f": "5,1", "c": "16,7", "kcal": "105,1", "output": OUT(100)},
        {"name": "Салат «Чайка» (сыр, зел. горошек, яйцо) с майонезом", "p": "2,50", "f": "4,70", "c": "7,30", "kcal": "201,40", "output": OUT(100)},
        {"name": "Сыр", "p": "23,7", "f": "30,5", "c": "0", "kcal": "377", "output": OUT(30)},
        {"name": "Яйцо отварное", "output": None},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с колбасой вареной (яйцо, молоко, масло)", "p": "16,5", "f": "12,9", "c": "12,5", "kcal": "229,6", "output": OUT(200)},
        {"name": "Биточки паровые (говядина, батон, без яйца), каша ячневая вязкая", "p": "12,2", "f": "20,4", "c": "11,2", "kcal": "403,0", "output": OUT(100 + 150)},
        {"name": "Биточки паровые (говядина, батон, без яйца), картофельно-гороховое пюре", "p": "22,2", "f": "9,9", "c": "25,8", "kcal": "277,9", "output": OUT(100 + 150)},
        {"name": "Печень (куриная) жареная с луком, каша ячневая вязкая", "p": "24,2", "f": "47,9", "c": "21,4", "kcal": "617,5", "output": OUT(75 + 150)},
        {"name": "Печень (куриная) жареная с луком, картофельно-гороховое пюре", "p": "34,8", "f": "48,6", "c": "25,4", "kcal": "665,0", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
    ], is_common=True)

    # 2-ой завтрак / полдник (snack) пропускаем

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Винегрет овощной с сельдью (зел. горошек, картофель, морковь, конс. огурец, свекла)", "p": "3,2", "f": "7,6", "c": "12,4", "kcal": "152,3", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров со сметаной", "p": "5,0", "f": "8,1", "c": "6,4", "kcal": "194,6", "output": OUT(100)},
        {"name": "Салат «Оливье по-лепельски» (куры, морковь, огурец марин., лук, майонез)", "p": "4,3", "f": "15,9", "c": "15,5", "kcal": "283,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Щи из капусты с картофелем со сметаной", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300)},
        {"name": "Суп картофельный с рыбными фрикадельками (хек, лук, яйцо)", "p": "2,7", "f": "10,2", "c": "11,4", "kcal": "144,0", "output": OUT(300 + 30)},
        {"name": "Суп молочный овсяный с хлопьями «Геркулес»", "p": "6,9", "f": "7,2", "c": "21,3", "kcal": "174,6", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Капуста цветная под молочным соусом", "p": "6,0", "f": "9,3", "c": "18,3", "kcal": "145,5", "output": OUT(250)},
        {"name": "Зразы рубленые запеченные (говядина, батон, молоко, яйцо), гречневая каша рассыпчатая", "p": "23,4", "f": "20,4", "c": "16,5", "kcal": "457,5", "output": OUT(100 + 150)},
        {"name": "Зразы рубленые запеченные (говядина, батон, молоко, яйцо), овощи отварные", "p": "20.1", "f": "18.3", "c": "20.9", "kcal": "432.7", "output": OUT(100 + 150)},
        {"name": "Жаркое с говядиной (картофель, лук, томат)", "p": "17,7", "f": "34,4", "c": "36,9", "kcal": "514,5", "output": OUT(75 + 200)},
        {"name": "Суфле паровое (куры, яйцо), овощи отварные", "p": "22,7", "f": "22,4", "c": "11,1", "kcal": "351,7", "output": OUT(100 + 150)},
        {"name": "Суфле паровое (куры, яйцо), гречневая каша рассыпчатая", "p": "22,7", "f": "22,4", "c": "11,1", "kcal": "351,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из помидоров с растит. маслом", "p": "1,2", "f": "9,2", "c": "11,2", "kcal": "107,3", "output": OUT(100)},
        {"name": "С-т из печени (печень гов., картофель, огурец, морковь) с майонезом", "p": "3,8", "f": "10,1", "c": "3,8", "kcal": "109,8", "output": OUT(100)},
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "3,5", "f": "3,6", "c": "6,9", "kcal": "175,2", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Рыба запеченная в сметане с луком (скумбрия), овсяная каша вязкая", "p": "25", "f": "17,6", "c": "9,3", "kcal": "367", "output": OUT(100 + 150)},
        {"name": "Рыба запеченная в майонезе с луком (скумбрия), картофельное пюре", "p": "21,2", "f": "12,5", "c": "11,2", "kcal": "452,2", "output": OUT(100 + 150)},
        {"name": "Шницель натуральный отбивной (свинина, сухари, яйцо), картофельное пюре", "p": "13,4", "f": "16,4", "c": "21,5", "kcal": "347,2", "output": OUT(90 + 150)},
        {"name": "Шницель натуральный отбивной (свинина, сухари, яйцо), овсяная каша вязкая", "p": "11,9", "f": "18.3", "c": "26,5", "kcal": "336,1", "output": OUT(90 + 150)},
        {"name": "Тефтели паровые (говядина, батон, молоко, без яйца), картофельное пюре", "p": "16,6", "f": "18,7", "c": "10,8", "kcal": "544", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые (говядина, батон, молоко, без яйца), овсяная каша вязкая", "p": "15,3", "f": "16,7", "c": "9,7", "kcal": "434", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный без сахара"},
        {"name": "Чай зеленый без сахара"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт б/с", "p": "5,6", "f": "6,4", "c": "8,2", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()