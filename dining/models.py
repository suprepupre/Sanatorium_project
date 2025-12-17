from django.db import models

from datetime import date


# Общие константы

DAY_OF_WEEK_CHOICES = [
    (1, "Понедельник"),
    (2, "Вторник"),
    (3, "Среда"),
    (4, "Четверг"),
    (5, "Пятница"),
    (6, "Суббота"),
    (7, "Воскресенье"),
]

MEAL_TIMES = {
    "breakfast": None,
    "lunch": "14:00",
    "dinner": "19:00",
}

MEAL_CHOICES = [
    ("breakfast", "Завтрак"),
    ("lunch", "Обед"),
    ("dinner", "Ужин"),
]

DIET_TYPE_CHOICES = [
    ("P", "П (пищевод)"),
    ("B", "Б (обычное)"),
    ("BD", "БД (диабетическое)"),
]

class DiningTable(models.Model):
    number = models.PositiveIntegerField(unique=True, verbose_name="Номер стола")
    places_count = models.PositiveIntegerField(default=4, verbose_name="Количество мест")

    def __str__(self):
        return f"Стол №{self.number}"
    class Meta:
        verbose_name = "Стол"
        verbose_name_plural = "Столы"

class Guest(models.Model):
    full_name = models.CharField(max_length=200, verbose_name="ФИО")
    start_date = models.DateField(verbose_name="Дата заезда")
    end_date = models.DateField(verbose_name="Дата выезда")
    access_code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Код доступа",
        help_text="Пароль для входа гостя",
    )
    diet_kind = models.CharField(
        max_length=10,
        choices=DIET_TYPE_CHOICES,
        default="B",
        verbose_name="Вид диеты (П/Б/БД)",
    )

    # Разрешённые приёмы пищи (обычные дни)
    breakfast_allowed = models.BooleanField(
        default=True, verbose_name="Завтрак", help_text="Разрешить выбор завтрака"
    )
    lunch_allowed = models.BooleanField(
        default=True, verbose_name="Обед", help_text="Разрешить выбор обеда"
    )
    snack_allowed = models.BooleanField(
        default=False, verbose_name="Полдник", help_text="Разрешить выбор полдника"
    )
    dinner_allowed = models.BooleanField(
        default=True, verbose_name="Ужин", help_text="Разрешить выбор ужина"
    )

    # --- НОВЫЕ ПОЛЯ ---
    departure_lunch = models.BooleanField(
        default=False,
        verbose_name="Обед в день выезда (платный)",
        help_text="Разрешить обед в последний день пребывания"
    )
    departure_dinner = models.BooleanField(
        default=False,
        verbose_name="Ужин в день выезда (платный)",
        help_text="Разрешить ужин в последний день пребывания"
    )

    class Meta:
        verbose_name = "Отдыхающий"
        verbose_name_plural = "Отдыхающие"

    def __str__(self):        
        return self.full_name


class SeatAssignment(models.Model):
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="seat_assignments",
        verbose_name="Отдыхающий",
    )
    table = models.ForeignKey(
        DiningTable,
        on_delete=models.CASCADE,
        verbose_name="Стол",
    )
    place_number = models.PositiveIntegerField(verbose_name="Место за столом")
    start_date = models.DateField(verbose_name="С какого числа")
    end_date = models.DateField(verbose_name="По какое число")

    class Meta:
        verbose_name = "Посадка за стол"
        verbose_name_plural = "Посадки за столы"

    def __str__(self):
        return f"{self.guest} — стол {self.table.number}, место {self.place_number}"


# --------- Меню и блюда ----------


class Dish(models.Model):
    """Справочник блюд"""
    
     # НОВОЕ ПОЛЕ:
    short_name = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Название для кухни/официантов",
        help_text="Если заполнено, официанты и кухня будут видеть это название (сокращенное). Если пусто — полное."
    )

    name = models.CharField(max_length=200, verbose_name="Название блюда")
    is_diet = models.BooleanField(default=False, verbose_name="Диетическое блюдо")

    proteins = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Белки, г"
    )
    fats = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Жиры, г"
    )
    carbs = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Углеводы, г"
    )
    kcal = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, verbose_name="Ккал"
    )
    output = models.PositiveSmallIntegerField(  # НОВОЕ ПОЛЕ
        null=True, blank=True, verbose_name="Выход, г"
    )

    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"
    
    def __str__(self):
        return self.name

class MenuCycle(models.Model):
    """
    Цикл меню — например, Меню №1 (7 дней), Меню №2 (7 дней)
    """

    name = models.CharField(max_length=100, verbose_name="Название меню")
    days_count = models.PositiveSmallIntegerField(default=7, verbose_name="Дней в цикле")

    class Meta:
        verbose_name = "Цикл меню"
        verbose_name_plural = "Циклы меню"

    def __str__(self):
        return self.name


class DailyMenu(models.Model):
    """
    Меню на конкретный день цикла, для одного типа (диетическое/обычное)
    """

    cycle = models.ForeignKey(
        MenuCycle, on_delete=models.CASCADE, related_name="daily_menus", verbose_name="Меню"
    )
    day_index = models.PositiveSmallIntegerField(
        choices=DAY_OF_WEEK_CHOICES,
        verbose_name="День недели",
    )
    diet_kind = models.CharField(
        max_length=10,
        choices=DIET_TYPE_CHOICES,
        default="B",
        verbose_name="Вид диеты (П/Б/БД)",
    )

    class Meta:
        unique_together = ("cycle", "day_index", "diet_kind")
        verbose_name = "Меню на день"
        verbose_name_plural = "Меню по дням"

    def __str__(self):
        return f"{self.cycle.name} — {self.get_day_index_display()} ({self.get_diet_kind_display()})"


class MenuItem(models.Model):
    """
    Строка в меню на день: приём пищи + раздел + блюдо
    """

    daily_menu = models.ForeignKey(
        DailyMenu, on_delete=models.CASCADE, related_name="items", verbose_name="Меню на день"
    )
    meal_time = models.CharField(
        max_length=10, choices=MEAL_CHOICES, verbose_name="Приём пищи"
    )
    category = models.CharField(
        max_length=50, blank=True, verbose_name="Раздел (ЗАКУСКИ, 1-е БЛЮДА и т.п.)"
    )
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, verbose_name="Блюдо")
    order_index = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Порядок в разделе",
    )

    is_common = models.BooleanField(
        default=False,
        verbose_name="Общее блюдо (выдаётся всем)",
    )

    class Meta:
        ordering = ["meal_time", "order_index", "-id"]
        verbose_name = "Позиция меню"
        verbose_name_plural = "Позиции меню"

    def __str__(self):
        return f"{self.get_meal_time_display()}: {self.dish.name}"


# ---------- Заказы гостей ----------


# class Order(models.Model):
  #  guest = models.ForeignKey(
   #     Guest, on_delete=models.CASCADE, related_name="orders", verbose_name="Отдыхающий"
    #)
    #date = models.DateField(verbose_name="Дата")
    #meal_time = models.CharField(
    #    max_length=10, choices=MEAL_CHOICES, verbose_name="Приём пищи"
    #)
    #created_at = models.DateTimeField(auto_now_add=True)

    # class Meta:
    #    unique_together = ("guest", "date", "meal_time")
    #   verbose_name = "Заказ"
    #    verbose_name_plural = "Заказы"

    #def __str__(self):
    #    return f"{self.guest} — {self.date} — {self.get_meal_time_display()}"


#class OrderItem(models.Model):
#    order = models.ForeignKey(
#        Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ"
#    )
#    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, verbose_name="Позиция меню")
#    class Meta:
#        verbose_name = "Позиция заказа"
#        verbose_name_plural = "Позиции заказа"
#    def __str__(self):
#        return f"{self.order}: {self.menu_item.dish.name}"
    
class Order(models.Model):
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Отдыхающий",
    )
    date = models.DateField(verbose_name="Дата")
    meal_time = models.CharField(
        max_length=10,
        choices=MEAL_CHOICES,           # уже объявлено выше
        verbose_name="Приём пищи",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("guest", "date", "meal_time")
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"{self.guest} — {self.date} — {self.get_meal_time_display()}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        verbose_name="Позиция меню",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.order}: {self.menu_item.dish.name}"
    
class MenuRotationConfig(models.Model):
    """
    Глобальные настройки чередования меню.
    Ожидаем одну запись (singleton).
    """
    base_date = models.DateField(
        default=date(2025, 12, 8),
        verbose_name="Базовая дата начала Меню №1 (понедельник)",
    )
    forced_cycle = models.ForeignKey(
        "MenuCycle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Принудительно использовать меню",
        help_text="Если не задано — используется автоматическое чередование.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройка чередования меню"
        verbose_name_plural = "Настройки чередования меню"

    def __str__(self):
        return "Настройки чередования меню"