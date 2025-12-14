from datetime import date, timedelta
import random

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

# Даты, на которые создаём заказы
DATES = [
    date(2025, 12, 11),
    date(2025, 12, 12),
    date(2025, 12, 13),
]

TABLES_RANGE = range(21, 31)     # тестовые столы 21..30
PLACES_PER_TABLE = 4
TEST_GUEST_PREFIX = "Тестовый гость"

today = date.today()
max_date = max(DATES) + timedelta(days=1)

print(f"Создаём тестовые заказы на даты: {', '.join(str(d) for d in DATES)}")


# --- создаём / находим тестовых гостей и посадку ---

test_guests = []

for table_number in TABLES_RANGE:
    table, _ = DiningTable.objects.get_or_create(
        number=table_number,
        defaults={"places_count": PLACES_PER_TABLE},
    )

    for place in range(1, PLACES_PER_TABLE + 1):
        full_name = f"{TEST_GUEST_PREFIX} {table_number}-{place}"

        guest, created = Guest.objects.get_or_create(
            full_name=full_name,
            defaults={
                "start_date": today,
                "end_date": max_date,
                "access_code": f"9{table_number:02d}{place}",
                "diet_kind": "regular",
            },
        )
        if not created:
            # обновим end_date, если нужно
            if guest.end_date < max_date:
                guest.end_date = max_date
                guest.save()

        # посадка за стол
        SeatAssignment.objects.get_or_create(
            guest=guest,
            table=table,
            place_number=place,
            defaults={"start_date": today, "end_date": guest.end_date},
        )

        test_guests.append(guest)

print(f"Тестовых гостей: {len(test_guests)}")


# --- получаем цикл меню ---

cycle = MenuCycle.objects.order_by("id").first()
if not cycle:
    print("ОШИБКА: нет MenuCycle. Сначала создай Меню №1.")
    raise SystemExit


# --- для каждой даты создаём заказы ---

for target_date in DATES:
    day_index = target_date.weekday() + 1
    daily_menu = DailyMenu.objects.filter(
        cycle=cycle,
        day_index=day_index,
        diet_kind="regular",
    ).first()

    if not daily_menu:
        print(f"ОШИБКА: нет DailyMenu для {target_date} (day_index={day_index}, regular). Пропускаем.")
        continue

    print(f"Создаём заказы на {target_date} ({day_index})")

    # блюда по приёмам пищи
    items_by_meal = {
        code: list(daily_menu.items.filter(meal_time=code, is_common=False))
        for code, _ in MEAL_CHOICES
    }

    created_orders = 0

    for guest in test_guests:
        # чистим старые заказы тестового гостя на эту дату
        Order.objects.filter(guest=guest, date=target_date).delete()

        for meal_code, label in MEAL_CHOICES:
            items = items_by_meal.get(meal_code) or []
            if not items:
                continue

            menu_item = random.choice(items)

            order = Order.objects.create(
                guest=guest,
                date=target_date,
                meal_time=meal_code,
            )
            OrderItem.objects.create(order=order, menu_item=menu_item)
            created_orders += 1

    print(f"  создано заказов: {created_orders}")

print("Готово.")