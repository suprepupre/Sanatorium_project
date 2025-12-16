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
TABLE_FROM = 31
TABLE_TO = 100
TARGET_DATE = date.today() + timedelta(days=1)  # ЗАВТРА
# =====================

# База имен для генерации
MALE_NAMES = [
    "Александр", "Сергей", "Владимир", "Андрей", "Алексей", "Николай", "Дмитрий", "Иван", 
    "Михаил", "Евгений", "Юрий", "Валерий", "Виктор", "Игорь", "Анатолий", "Олег", "Павел"
]
FEMALE_NAMES = [
    "Елена", "Татьяна", "Наталья", "Ольга", "Светлана", "Ирина", "Людмила", "Галина", 
    "Екатерина", "Анна", "Валентина", "Мария", "Нина", "Любовь", "Надежда", "Марина"
]
SURNAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", 
    "Новиков", "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семенов", "Егоров", 
    "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин", 
    "Захаров", "Зайцев", "Соловьев", "Борисов", "Яковлев", "Григорьев", "Романов", "Воробьев"
]

def generate_random_name():
    """Генерирует случайное ФИО."""
    gender = random.choice(['m', 'f'])
    surname = random.choice(SURNAMES)
    
    if gender == 'm':
        name = random.choice(MALE_NAMES)
        full_surname = surname
    else:
        name = random.choice(FEMALE_NAMES)
        # Делаем женскую фамилию (Иванов -> Иванова)
        full_surname = surname + "а"
    
    return f"{full_surname} {name}"

def get_cycle_and_day(target_date):
    """Определяем активное меню на дату."""
    cfg, _ = MenuRotationConfig.objects.get_or_create(id=1)
    cycles = list(MenuCycle.objects.order_by("id"))
    if not cycles:
        return None, None

    day_index = target_date.weekday() + 1  # 1=Пн .. 7=Вс

    if cfg.forced_cycle:
        return cfg.forced_cycle, day_index

    base_date = cfg.base_date
    days_diff = (target_date - base_date).days
    week_index = days_diff // 7
    cycle = cycles[week_index % len(cycles)]
    
    return cycle, day_index

@transaction.atomic
def main():
    print(f"--- Генерация данных на {TARGET_DATE} (Столы {TABLE_FROM}-{TABLE_TO}) ---")

    # 1. Чистим места на этих столах, чтобы не было конфликтов
    print("Очистка старых данных на выбранных столах...")
    # Находим посадки, пересекающиеся с завтра
    seats_to_clear = SeatAssignment.objects.filter(
        table__number__range=(TABLE_FROM, TABLE_TO),
        start_date__lte=TARGET_DATE,
        end_date__gte=TARGET_DATE
    )
    # Удаляем гостей (каскадно удалит посадки и заказы)
    for seat in seats_to_clear:
        seat.guest.delete()

    # 2. Определяем меню
    cycle, day_index = get_cycle_and_day(TARGET_DATE)
    if not cycle:
        print("ОШИБКА: Нет циклов меню.")
        return
    print(f"Меню: {cycle.name}, День недели: {day_index}")

    # 3. Кэшируем блюда
    # diet_items[diet_code][meal_code] = [MenuItem, ...]
    diet_items = {}
    for diet in ["B", "P", "BD"]:
        dm = DailyMenu.objects.filter(
            cycle=cycle, day_index=day_index, diet_kind=diet
        ).first()
        
        if not dm:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Нет меню для {diet} на завтра!")
            continue
            
        diet_items[diet] = {}
        for meal, _ in MEAL_CHOICES:
            # Берем только то, что можно выбрать (не is_common)
            items = list(dm.items.filter(meal_time=meal, is_common=False))
            diet_items[diet][meal] = items

    # 4. Рассадка и заказы
    count = 0
    diets_pool = ["B", "B", "B", "P", "BD"] # B чаще

    for t_num in range(TABLE_FROM, TABLE_TO + 1):
        table, _ = DiningTable.objects.get_or_create(
            number=t_num, defaults={"places_count": 4}
        )

        for p_num in range(1, 5):
            full_name = generate_random_name()
            diet = random.choice(diets_pool)
            
            # Уникальный код доступа
            code = f"{t_num}{p_num}{random.randint(10,99)}"
            
            guest = Guest.objects.create(
                full_name=full_name,
                start_date=TARGET_DATE,
                end_date=TARGET_DATE + timedelta(days=7),
                access_code=code,
                diet_kind=diet,
                snack_allowed=False
            )
            
            SeatAssignment.objects.create(
                guest=guest,
                table=table,
                place_number=p_num,
                start_date=TARGET_DATE,
                end_date=TARGET_DATE + timedelta(days=7)
            )

            # Делаем заказ
            available_meals = diet_items.get(diet, {})
            for meal, _ in MEAL_CHOICES:
                options = available_meals.get(meal, [])
                if options:
                    # Случайный выбор блюда
                    chosen = random.choice(options)
                    order = Order.objects.create(
                        guest=guest,
                        date=TARGET_DATE,
                        meal_time=meal
                    )
                    OrderItem.objects.create(order=order, menu_item=chosen)
            
            count += 1

    print(f"Готово! Заселено {count} гостей с заказами.")

main()