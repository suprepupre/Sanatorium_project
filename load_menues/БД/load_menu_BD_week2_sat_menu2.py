import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "BD"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 6            # Суббота


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
        # общие позиции (хлеб/чай/батон/масло/печенье и т.п.) не помечаем как diet=True
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

    # перезаписываем только этот день (Сб, Меню №2, БД)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        {"name": "Компот из кураги без сахара", "p": "1,4", "f": "0,0", "c": "20,8", "kcal": "87,4", "output": OUT(200)},
        {"name": "Сок томатный", "p": "0,0", "f": "0,2", "c": "10,0", "kcal": "38,0", "output": OUT(200)},
        {"name": "Молоко", "p": "0,6", "f": "0,4", "c": "9,5", "kcal": "56", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат «Витаминный» (капуста, яблоко, морковь) с растит. маслом", "p": "1,2", "f": "5,2", "c": "11,0", "kcal": "94,1", "output": OUT(100)},
        {"name": "Салат «Новинка» (конс. рыбные, рис, яблоко, огурец мар., яйцо, майонез)", "p": "7,3", "f": "17.4", "c": "17.2", "kcal": "262.7", "output": OUT(100)},
        {"name": "Творог со сметаной", "p": "17.1", "f": "12", "c": "2.4", "kcal": "138,5", "output": OUT(80)},
        {"name": "Абрикос (сушеный)", "output": OUT(30)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Капуста брокколи запеченная с сыром (молоко, мука, сыр)", "p": "3,4", "f": "6,9", "c": "7,7", "kcal": "106,7", "output": OUT(200)},
        {"name": "Котлеты полтавские жареные (св-гов, сухари, чеснок), картофельно-гороховое пюре", "p": "24,9", "f": "24,4", "c": "26,4", "kcal": "601", "output": OUT(100 + 150)},
        {"name": "Котлеты полтавские жареные (св-гов, сухари, чеснок), гречневая каша вязкая", "p": "21,3", "f": "24,0", "c": "32,7", "kcal": "599,5", "output": OUT(100 + 150)},
        {"name": "Птица отварная, картофельно-гороховое пюре", "p": "28,4", "f": "49,2", "c": "25,1", "kcal": "669,6", "output": OUT(75 + 150)},
        {"name": "Птица отварная, гречневая каша вязкая", "p": "24,8", "f": "48,8", "c": "31,4", "kcal": "668,1", "output": OUT(75 + 150)},
        {"name": "Котлеты паровые (говядина, батон, молоко), гречневая каша вязкая", "p": "13,3", "f": "15", "c": "33,6", "kcal": "339,9", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Масло"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    # 2-ой завтрак — как общая категория внутри завтрака
    add_block(daily_menu, "breakfast", "ВТОРОЙ ЗАВТРАК", [
        {"name": "Сок томатный"},
        {"name": "Печенье на фруктозе"},
        {"name": "Сок фруктовый без сахара"},
        {"name": "Печенье на фруктозе"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из огурца и свеклы с растит. маслом", "p": "1,9", "f": "3,5", "c": "16,5", "kcal": "97,4", "output": OUT(100)},
        {"name": "Салат из белокочанной капусты и помидоров со сметаной", "p": "1,9", "f": "0,1", "c": "3,1", "kcal": "119", "output": OUT(100)},
        {"name": "Салат овощной с колбасой (картофель, горошек, огурец мар., майонез)", "p": "4,7", "f": "18,6", "c": "2,8", "kcal": "200,7", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Суп картофельный с фрикадельками (свин-гов, лук, яйцо)", "p": "0,7", "f": "0,9", "c": "5,2", "kcal": "31,8", "output": OUT(300 + 30)},
        {"name": "Суп картофельный с горохом", "p": "2,1", "f": "1,8", "c": "7,9", "kcal": "56,8", "output": OUT(300 + 30)},
        {"name": "Суп картофельный с хлопьями «Геркулес»", "p": "0,9", "f": "0,9", "c": "6,2", "kcal": "37,5", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Голубцы, фаршированные овощами и рисом (сладкий перец, морковь, томат, лук, мука)", "p": "2,6", "f": "5,9", "c": "12,3", "kcal": "283,3", "output": OUT(200)},
        {"name": "Гуляш из говядины, каша ячневая вязкая", "p": "28,9", "f": "17", "c": "19.3", "kcal": "544", "output": OUT(75 + 150)},
        {"name": "Гуляш из говядины, овощи отварные (капуста, морковь, горошек)", "p": "29,3", "f": "16,8", "c": "12,1", "kcal": "512,9", "output": OUT(75 + 150)},
        {"name": "Зразы куриные паровые (яйцо, батон, молоко), овощи отварные (капуста, морковь, горошек)", "p": "17,5", "f": "14,5", "c": "13,7", "kcal": "273,6", "output": OUT(100 + 150)},
        {"name": "Зразы куриные паровые (яйцо, батон, молоко), каша ячневая вязкая", "p": "17,1", "f": "15", "c": "20.9", "kcal": "304,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Компот без сахара"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты, лука и сладкого перца с растит. маслом", "p": "1,3", "f": "20", "c": "4,9", "kcal": "204,6", "output": OUT(100)},
        {"name": "С-т «Несвижский» (сельдь, свекла, картофель, лук) с майонезом", "p": "9", "f": "15,3", "c": "5,2", "kcal": "187,5", "output": OUT(100)},
        {"name": "Салат «Розовый» (морковь, свекла, яйцо, лук) со сметаной", "p": "5,2", "f": "17,2", "c": "4,2", "kcal": "197,1", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "5,3", "f": "7,4", "c": "28,7", "kcal": "176,8", "output": OUT(200)},
        {"name": "Тефтели паровые с рисом (говядина, без яйца), перловая каша рассыпчатая/соус", "p": "16,3", "f": "21,3", "c": "29,3", "kcal": "376,6", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в майонезе (горбуша, лук, мука), картофельное пюре", "p": "24,0", "f": "25,4", "c": "18,3", "kcal": "386", "output": OUT(100 + 150)},
        {"name": "Рыба, запеченная в майонезе (горбуша, лук, мука), перловая каша рассыпчатая/соус", "p": "25,0", "f": "25,5", "c": "26,3", "kcal": "422,5", "output": OUT(100 + 150)},
        {"name": "Рулет (натуральный) из свинины с черносливом, картофельное пюре", "p": "22,6", "f": "48,6", "c": "24,6", "kcal": "630,1", "output": OUT(75 + 150)},
        {"name": "Рулет (натуральный) из свинины с черносливом, перловая каша рассыпчатая", "p": "23,6", "f": "48,7", "c": "32,6", "kcal": "666,6", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт б/с", "output": None},  # в тексте "1"
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()