import random
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone

from dining.models import (
    Guest, SeatAssignment, DiningTable,
    MenuCycle, DailyMenu, Order, OrderItem,
    MenuRotationConfig, MEAL_CHOICES
)

# ===== НАСТРОЙКИ =====
TABLE_FROM = 1
TABLE_TO = 30           # Заполним 30 столов (120 человек)
TARGET_DATE = date.today() + timedelta(days=1)
# =====================

def get_cycle_and_day(target_date):
    """Определяем, какое меню активно на указанную дату"""
    cfg, _ = MenuRotationConfig.objects.get_or_create(id=1)
    cycles = list(MenuCycle.objects.order_by("id"))
    if not cycles:
        return None, None

    day_index = target_date.weekday() + 1  # 1=Пн .. 7=Вс

    # Если принудительно выбрано
    if cfg.forced_cycle:
        return cfg.forced_cycle, day_index

    # Автоматическое чередование
    base_date = cfg.base_date
    days_diff = (target_date - base_date).days
    week_index = days_diff // 7
    cycle = cycles[week_index % len(cycles)]
    
    return cycle, day_index

@transaction.atomic
def main():
    print(f"--- Создаём заказы на ЗАВТРА: {TARGET_DATE} ---")

    # 1. Удаляем старых тестовых гостей (чтобы не мешали)
    Guest.objects.filter(full_name__startswith="ТестГость").delete()
    print("Старые тестовые гости удалены.")

    # 2. Определяем меню
    cycle, day_index = get_cycle_and_day(TARGET_DATE)
    if not cycle:
        print("ОШИБКА: Нет циклов меню в базе.")
        return

    print(f"Активное меню: {cycle.name}, День: {day_index}")

    # 3. Загружаем варианты блюд для всех диет
    # diet_menus[diet_kind][meal_time] = [MenuItem, MenuItem...]
    diet_menus = {}
    
    for diet in ["B", "P", "BD"]:
        dm = DailyMenu.objects.filter(
            cycle=cycle, day_index=day_index, diet_kind=diet
        ).first()
        
        if not dm:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Нет меню для диеты {diet} на этот день.")
            diet_menus[diet] = {}
            continue

        diet_menus[diet] = {}
        for meal_code, _ in MEAL_CHOICES:
            # Берем только блюда по выбору (не общие)
            items = list(dm.items.filter(meal_time=meal_code, is_common=False))
            diet_menus[diet][meal_code] = items

    # 4. Создаём гостей и заказы
    count_guests = 0
    count_orders = 0

    diets_pool = ["B", "B", "P", "BD"] # Распределение диет

    for table_num in range(TABLE_FROM, TABLE_TO + 1):
        # Создаем стол если нет
        table, _ = DiningTable.objects.get_or_create(
            number=table_num, defaults={"places_count": 4}
        )

        for place in range(1, 5):
            # Пропускаем, если место занято РЕАЛЬНЫМ человеком (не тестовым)
            if SeatAssignment.objects.filter(
                table=table, place_number=place,
                start_date__lte=TARGET_DATE, end_date__gte=TARGET_DATE
            ).exists():
                continue

            diet = random.choice(diets_pool)
            
            # Создаем гостя
            guest = Guest.objects.create(
                full_name=f"ТестГость {table_num}-{place} ({diet})",
                start_date=TARGET_DATE,
                end_date=TARGET_DATE + timedelta(days=5),
                access_code=f"t{table_num}-{place}",
                diet_kind=diet,
                snack_allowed=False
            )
            
            SeatAssignment.objects.create(
                guest=guest, table=table, place_number=place,
                start_date=TARGET_DATE, end_date=TARGET_DATE + timedelta(days=5)
            )
            count_guests += 1

            # Формируем заказ
            # Берем доступные блюда для этой диеты
            available_meals = diet_menus.get(diet, {})
            
            for meal_code, _ in MEAL_CHOICES:
                options = available_meals.get(meal_code, [])
                if not options:
                    continue
                
                # Выбираем случайное блюдо
                selected_item = random.choice(options)
                
                order = Order.objects.create(
                    guest=guest,
                    date=TARGET_DATE,
                    meal_time=meal_code
                )
                OrderItem.objects.create(order=order, menu_item=selected_item)
                count_orders += 1

    print(f"Готово! Создано гостей: {count_guests}, Заказов: {count_orders}")
    print(f"Проверь: http://localhost:8000/waiter/?date={TARGET_DATE}")

main()