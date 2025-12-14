from datetime import date, timedelta
import random

from django.db import transaction

from dining.models import (
    DiningTable,
    Guest,
    SeatAssignment,
    MenuCycle,
    DailyMenu,
    MenuItem,
    Order,
    OrderItem,
    MEAL_CHOICES,
)

# ===== НАСТРОЙКИ =====
TEST_PREFIX = "ТЕСТ"
TABLE_FROM = 73     
TABLE_TO =  88        # включительно (91..95 = 5 столов)
PLACES_PER_TABLE = 4
TARGET_DATE = date.today() + timedelta(days=2)   # на какую дату создаём заказы
ORDER_RATE = 0.6        # доля гостей, которые "выбрали меню" (0.6 = 60%)
DIETS = ["P", "B", "BD"] # виды диеты

MAX_TABLE_NUMBER = 100
# =====================

def get_cycle_for_date(d: date):
    cycles = list(MenuCycle.objects.order_by("id"))
    if not cycles:
        return None, None
    day_index = d.weekday() + 1  # 1..7

    # чередование по неделям — как в вашем проекте
    # IMPORTANT: синхронизировать с BASE_MENU_CYCLE_DATE в views.py!
    BASE_MENU_CYCLE_DATE = date(2025, 12, 8)  # понедельник Меню №1
    days_diff = (d - BASE_MENU_CYCLE_DATE).days
    week_index = days_diff // 7
    cycle = cycles[week_index % len(cycles)]

    return cycle, day_index

def diet_digit(code: str) -> str:
    return {"P": "1", "B": "2", "BD": "3"}.get(code, "9")

def make_unique_code(base: str) -> str:
    # гарантируем уникальность access_code
    code = base
    while Guest.objects.filter(access_code=code).exists():
        code = base + str(random.randint(0, 9))
    return code

@transaction.atomic
def main():
    print("TARGET_DATE =", TARGET_DATE)

    # 1) Удаляем старых тестовых гостей
    old = Guest.objects.filter(full_name__startswith=TEST_PREFIX)
    if old.exists():
        print("Удаляем старых тестовых гостей:", old.count())
        old.delete()

    # 2) Проверяем, что есть циклы меню
    cycles = list(MenuCycle.objects.order_by("id"))
    if not cycles:
        print("ОШИБКА: нет MenuCycle (Меню №1/№2).")
        return

    cycle, day_index = get_cycle_for_date(TARGET_DATE)
    print("Активный цикл на дату:", cycle.name if cycle else None, "day_index:", day_index)

    created_guests = 0
    created_orders = 0
    skipped_seats = 0

    # 3) Создаём гостей по столам/местам
    diet_i = 0
    for table_no in range(TABLE_FROM, TABLE_TO + 1):
        if table_no < 1 or table_no > MAX_TABLE_NUMBER:
            continue

        table, _ = DiningTable.objects.get_or_create(number=table_no, defaults={"places_count": PLACES_PER_TABLE})

        for place_no in range(1, PLACES_PER_TABLE + 1):
            # если место уже занято реальным гостем на TARGET_DATE — пропускаем
            if SeatAssignment.objects.filter(
                table=table,
                place_number=place_no,
                start_date__lte=TARGET_DATE,
                end_date__gte=TARGET_DATE,
            ).exists():
                skipped_seats += 1
                continue

            diet_code = DIETS[diet_i % len(DIETS)]
            diet_i += 1

            full_name = f"{TEST_PREFIX} {diet_code} {table_no}-{place_no}"
            end_date = TARGET_DATE + timedelta(days=10)

            base_code = f"7{table_no:02d}{place_no}{diet_digit(diet_code)}"
            access_code = make_unique_code(base_code)

            guest = Guest.objects.create(
                full_name=full_name,
                start_date=date.today(),
                end_date=end_date,
                access_code=access_code,
                diet_kind=diet_code,
            )

            SeatAssignment.objects.create(
                guest=guest,
                table=table,
                place_number=place_no,
                start_date=date.today(),
                end_date=end_date,
            )

            created_guests += 1

            # 4) Часть гостей делает "выбор меню", часть — нет
            if random.random() > ORDER_RATE:
                continue  # этот гость НЕ выбирал меню

            # находим меню на эту дату под его диету
            daily_menu = DailyMenu.objects.filter(
                cycle=cycle,
                day_index=day_index,
                diet_kind=diet_code,
            ).first()

            if not daily_menu:
                # если меню этой диеты не заведено, пропустим заказы
                continue

            # для каждого приёма пищи выберем 1 случайное блюдо (не общее)
            for meal_code, _label in MEAL_CHOICES:
                items = list(
                    daily_menu.items.filter(meal_time=meal_code, is_common=False)
                    .select_related("dish")
                    .order_by("order_index", "id")
                )
                if not items:
                    continue

                chosen = random.choice(items)
                order = Order.objects.create(
                    guest=guest,
                    date=TARGET_DATE,
                    meal_time=meal_code,
                )
                OrderItem.objects.create(order=order, menu_item=chosen)
                created_orders += 1

    print("Создано гостей:", created_guests)
    print("Создано заказов:", created_orders)
    print("Пропущено мест (занято реальными):", skipped_seats)
    print("Готово.")

main()