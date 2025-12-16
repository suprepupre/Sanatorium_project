import re
from decimal import Decimal
from django.db import transaction

from dining.models import Dish, MenuCycle, DailyMenu, MenuItem

DIET_KIND = "B"
CYCLE_NAME = "Меню №2"   # "3"
DAY_INDEX = 3            # Среда
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

    # очищаем только этот день (Ср, Меню №2, Диета Б)
    daily_menu.items.all().delete()

    # ===================== ЗАВТРАК =====================
    add_block(daily_menu, "breakfast", "НАПИТКИ", [
        # В тексте ккал "420," — трактую как 42,0 (иначе явный мусор)
        {"name": "Нектар фруктовый", "p": "0,2", "f": "0,0", "c": "10,3", "kcal": "42,0", "output": OUT(200)},
        {"name": "Сок томатный",     "p": "0,0", "f": "0,0", "c": "17,0", "kcal": "34,0", "output": OUT(200)},
        {"name": "Компот из кураги без сахара", "p": "0,0", "f": "0,0", "c": "6,5", "kcal": "24,6", "output": OUT(200)},
        {"name": "Молоко",           "p": "2,8", "f": "1,5", "c": "4,8",  "kcal": "44,0", "output": OUT(200)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ЗАКУСКИ", [
        {"name": "Салат из белокочанной капусты, лука, сладкого перца с растит. маслом", "p": "1,9", "f": "18,1", "c": "4,5", "kcal": "187,3", "output": OUT(100)},
        {"name": "Салат «Скорый» (варёная колбаса, огурец мар., морковь, лук, томат) с майонезом", "p": "1,0", "f": "10,2", "c": "3,5", "kcal": "110", "output": OUT(100)},
        {"name": "Йогурт", "output": OUT(200)},  # в тексте видно "200", БЖУ/ккал не указаны
        {"name": "Каша пшенная молочная", "p": "4,5", "f": "5,4", "c": "17,9", "kcal": "110,3", "output": OUT(100)},
        {"name": "Творог со сметаной и сахаром", "p": "17,1", "f": "12,5", "c": "2,4", "kcal": "185,8", "output": OUT(80)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "2-е БЛЮДА", [
        {"name": "Омлет с сыром (молоко, яйцо, сыр)", "p": "12,1", "f": "19,0", "c": "1,7", "kcal": "227,0", "output": OUT(200)},
        {"name": "Запеканка рисовая с яблоками со сметаной", "p": "3,3", "f": "6,0", "c": "21,2", "kcal": "149,1", "output": OUT(200 + 20)},
        {"name": "Свинина по-деревенски (сметана, лук), капуста тушеная", "p": "23,2", "f": "52,1", "c": "0,6", "kcal": "499,2", "output": OUT(75 + 150)},  # 75//150
        {"name": "Свинина по-деревенски (сметана, лук), макароны отварные", "p": "23,2", "f": "52,1", "c": "0,6", "kcal": "499,2", "output": OUT(75 + 150)},  # 75//150
        # "100/1500" трактую как 100/150 => 250
        {"name": "Котлеты паровые (говядина, батон), капуста тушеная", "p": "18,8", "f": "20,9", "c": "24,2", "kcal": "321,1", "output": OUT(100 + 150)},
        {"name": "Котлеты паровые (говядина, батон), макароны отварные, соус", "p": "16,8", "f": "20,8", "c": "32,5", "kcal": "356,7", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "breakfast", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Какао с молоком"},
        {"name": "Масло"},
    ], is_common=True)

    # ===================== ОБЕД =====================
    add_block(daily_menu, "lunch", "ЗАКУСКИ", [
        {"name": "Салат из моркови с изюмом со сметаной", "p": "1,6", "f": "3,5", "c": "19,7", "kcal": "107,7", "output": OUT(100)},
        {"name": "Салат из помидоров и сладкого перца с растит. маслом", "p": "3,6", "f": "9,7", "c": "4,9", "kcal": "123,0", "output": OUT(100)},
        {"name": "Салат «Смак» (куры, рис, яйцо, сыр, курага, майонез)", "p": "2,3", "f": "27,5", "c": "3,7", "kcal": "154,4", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "1-е БЛЮДА", [
        {"name": "Борщ сибирский (фасоль, лук, томат) со сметаной", "p": "1,0", "f": "2,3", "c": "6,8", "kcal": "33,2", "output": OUT(300)},
        {"name": "Суп картофельный с рисом (картофель, морковь, лук)", "p": "2,3", "f": "2,3", "c": "5,0", "kcal": "49,1", "output": OUT(300)},
        {"name": "Суп молочный с овощами (морковь, картофель, стручк. фасоль, капуста, без муки)", "p": "2,0", "f": "1,5", "c": "4,8", "kcal": "40,2", "output": OUT(300)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "2-е БЛЮДА", [
        {"name": "Морковь тушеная с черносливом", "p": "7,0", "f": "14,7", "c": "18,5", "kcal": "229,8", "output": OUT(200)},
        {"name": "Бабка картофельная со свининой (картофель тёртый, лук, чеснок, мука, сметана)", "p": "9,3", "f": "17,7", "c": "5,5", "kcal": "218,0", "output": OUT(270)},
        {"name": "Котлеты «Оригинальные» (куры, морковь, сухари), овощи отварные", "p": "14,9", "f": "18,0", "c": "12,4", "kcal": "306,2", "output": OUT(100 + 150)},
        {"name": "Котлеты «Оригинальные» (куры, морковь, сухари), каша пшеничная", "p": "18,0", "f": "19,7", "c": "31,4", "kcal": "413,8", "output": OUT(100 + 150)},
        {"name": "Говядина отварная под белым соусом, овощи отварные (капуста, морковь, горошек)", "p": "20,7", "f": "16,2", "c": "37,1", "kcal": "438,1", "output": OUT(75 + 150)},
        {"name": "Говядина отварная под белым соусом, каша пшеничная", "p": "18,8", "f": "16,2", "c": "27,2", "kcal": "381,1", "output": OUT(75 + 150)},
        {"name": "Печень (говяжья) жареная с луком, каша пшеничная", "p": "32,9", "f": "21,4", "c": "40,1", "kcal": "454,5", "output": OUT(75 + 150)},
        {"name": "Печень (говяжья) жареная с луком, овощи отварные (капуста, морковь, горошек)", "p": "27,8", "f": "17", "c": "26", "kcal": "381,4", "output": OUT(75 + 150)},
    ], is_common=False)

    add_block(daily_menu, "lunch", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Кисель"},
    ], is_common=True)

    # ===================== УЖИН =====================
    add_block(daily_menu, "dinner", "ЗАКУСКИ", [
        {"name": "С-т «Русалочка» (горошек, краб. палочки, огурец, морская капуста, яйцо, лук) с майонезом", "p": "5,3", "f": "14,5", "c": "11,8", "kcal": "204,2", "output": OUT(100)},
        {"name": "Салат из свеклы с черносливом со сметаной", "p": "1,8", "f": "3,5", "c": "18,6", "kcal": "106,9", "output": OUT(100)},
        {"name": "Салат из огурцов и помидоров с растит. маслом", "p": "0,6", "f": "10,1", "c": "1,7", "kcal": "99,9", "output": OUT(100)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "2-е БЛЮДА", [
        {"name": "Капуста брокколи с сыром под соусом", "p": "3,4", "f": "6,9", "c": "7,7", "kcal": "106,7", "output": OUT(250)},
        {"name": "Тефтели паровые (говядина, без яйца, без муки), перловая каша вязкая", "p": "12,1", "f": "14,4", "c": "22,1", "kcal": "286,4", "output": OUT(100 + 150)},
        {"name": "Тефтели паровые (говядина, без яйца, без муки), картофельное пюре", "p": "12,2", "f": "14,9", "c": "22,4", "kcal": "293,1", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), картофельное пюре", "p": "20,4", "f": "5,0", "c": "13,8", "kcal": "181,2", "output": OUT(100 + 150)},
        {"name": "Рыба отварная (горбуша), перловая каша вязкая", "p": "20,3", "f": "4,5", "c": "13,5", "kcal": "174,5", "output": OUT(100 + 150)},
        {"name": "Филе из птицы, запечённое с сыром, перловая каша вязкая", "p": "18,9", "f": "37,56", "c": "13,1", "kcal": "386,8", "output": OUT(100 + 150)},
        {"name": "Филе из птицы, запечённое с сыром, картофельное пюре", "p": "19,0", "f": "38,0", "c": "13,4", "kcal": "393,5", "output": OUT(100 + 150)},
    ], is_common=False)

    add_block(daily_menu, "dinner", "ДОПОЛНИТЕЛЬНО", [
        {"name": "Хлеб"},
        {"name": "Батон"},
        {"name": "Выпечка"},
        {"name": "Чай черный"},
        {"name": "Чай зеленый"},
    ], is_common=True)

    add_block(daily_menu, "dinner", "НАПИТКИ", [
        {"name": "Йогурт", "p": "6,2", "f": "5,6", "c": "8,0", "kcal": "112", "output": OUT(200)},
        {"name": "Молоко", "p": "5,6", "f": "6,4", "c": "9,5", "kcal": "116", "output": OUT(200)},
    ], is_common=False)

    print("Готово:", daily_menu)

main()