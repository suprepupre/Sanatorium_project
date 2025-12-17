import random
import string
import re   

from urllib.parse import urlencode

from django.db.models import Q, Count
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date, datetime, time, timedelta
from functools import wraps
from django.db.models.deletion import ProtectedError


from .forms import (
    AddGuestForm,
    DishForm,
    DailyMenuSelectForm,
    MenuItemForm,
    GuestLoginForm,
    GuestMealsForm,
    AddGuestAtTableForm,
    GuestDepartureForm,
)

from .models import (
    DiningTable,
    Guest,
    SeatAssignment,
    Dish,
    MenuCycle,
    DailyMenu,
    MenuItem,
    Order,
    OrderItem,
    MEAL_CHOICES,
    DIET_TYPE_CHOICES,
    MEAL_TIMES,
    MenuRotationConfig,
)



WAITER_RANGES = {
    1: (1, 20),
    2: (21, 40),
    3: (41, 60),
    4: (61, 80),
    5: (81, 100),
}

MAX_TABLE_NUMBER = 100

CATEGORY_ORDER = {
    "НАПИТКИ": 10,
    "ЗАКУСКИ": 20,
    "1-Е БЛЮДА": 30,
    "1-е БЛЮДА": 30,       # на всякий случай
    "ПЕРВЫЕ БЛЮДА": 30,
    "2-Е БЛЮДА": 40,
    "2-е БЛЮДА": 40,       # если где-то с маленькой буквой
    "ВТОРЫЕ БЛЮДА": 40,
    "ДОПОЛНИТЕЛЬНО": 50,
}

def category_sort_key(name: str) -> tuple[int, str]:
    """
    Ключ сортировки разделов (категорий) меню.
    Сначала фиксированный порядок (НАПИТКИ, ЗАКУСКИ, 1-е, 2-е, ДОПОЛНИТЕЛЬНО),
    затем по алфавиту.
    """
    norm = (name or "").strip()
    return (CATEGORY_ORDER.get(norm.upper(), 100), norm)

def common_word_prefix(names: list[str]) -> str:
    """
    Возвращает общий префикс по словам для списка названий.
    Например:
      ["Куры отварные, каша гречневая",
       "Куры отварные, картофельное пюре"]
    -> "Куры отварные,".

    Если общий префикс слишком короткий (меньше 2 слов) — считаем,
    что он не информативен, и возвращаем пустую строку.
    """
    if len(names) < 2:
        return ""

    # разбиваем на слова
    split = [n.strip().split() for n in names if n.strip()]
    if not split:
        return ""

    min_len = min(len(words) for words in split)
    prefix_words = []

    for i in range(min_len):
        w = split[0][i]
        if all(words[i] == w for words in split[1:]):
            prefix_words.append(w)
        else:
            break

    # требуем хотя бы 2 общих слова, иначе не обрезаем
    if len(prefix_words) >= 2:
        return " ".join(prefix_words)
    return ""

BASE_MENU_CYCLE_DATE = date(2025, 12, 8)  # ПОНЕДЕЛЬНИК, с которого началось Меню №1


def allowed_meals_for_guest_on_date(guest: Guest, target_date: date) -> dict[str, bool]:
    """
    Возвращает какие приёмы пищи гостю РАЗРЕШЕНЫ на target_date.

    В обычные дни:
      breakfast_allowed / lunch_allowed / dinner_allowed

    В день выезда (target_date == guest.end_date):
      - завтрак: breakfast_allowed
      - обед: departure_lunch
      - ужин: departure_dinner

    ВАЖНО: lunch_allowed/dinner_allowed в день выезда НЕ ограничивают платные,
    иначе получится путаница. Решение: в выездной день смотрим только departure_*.
    """
    if target_date == guest.end_date:
        return {
            "breakfast": bool(guest.breakfast_allowed),
            "lunch": bool(guest.departure_lunch),
            "dinner": bool(guest.departure_dinner),
        }

    return {
        "breakfast": bool(guest.breakfast_allowed),
        "lunch": bool(guest.lunch_allowed),
        "dinner": bool(guest.dinner_allowed),
    }


def get_daily_menu_for_date_and_diet(target_date: date, diet_kind: str) -> DailyMenu | None:
    """Получаем дневное меню (DailyMenu) на дату и диету."""
    cycle, day_index = get_cycle_and_day_for_date(target_date)
    if not cycle:
        return None
    return DailyMenu.objects.filter(cycle=cycle, day_index=day_index, diet_kind=diet_kind).first()

def build_meal_blocks_from_daily_menu(daily_menu: DailyMenu):
    """
    Строит структуру meal_blocks для работы и в missing_menu_view, и в missing_menu_fill_view.

    Возвращает список:
    [
      {
        "code": "breakfast",
        "label": "Завтрак",
        "time": "08:00" или None,
        "categories": [
            { "key": "breakfast_cat_0", "category": "НАПИТКИ", "items": [MenuItem,...] },
            { "key": "breakfast_cat_1", "category": "ЗАКУСКИ", "items": [...] },
            ...
        ]
      },
      ...
    ]
    """
    meal_blocks = []

    for meal_code, meal_label in MEAL_CHOICES:
        # Берём все позиции этого приёма пищи
        items = list(
            daily_menu.items
            .filter(meal_time=meal_code)
            .select_related("dish")
            .order_by("order_index", "id")
        )
        if not items:
            continue

        # Группируем по category
        cat_map: dict[str, list[MenuItem]] = {}
        for it in items:
            cat = it.category or ""
            cat_map.setdefault(cat, []).append(it)

        # Собираем категории в нужном порядке (НАПИТКИ, ЗАКУСКИ, 1-е, 2-е, ДОПОЛНИТЕЛЬНО)
        categories = []
        idx = 0
        for cat_name, cat_items in sorted(
            cat_map.items(), key=lambda kv: category_sort_key(kv[0])
        ):
            key = f"{meal_code}_cat_{idx}"
            categories.append({
                "key": key,
                "category": cat_name,
                "items": cat_items,
            })
            idx += 1

        meal_blocks.append({
            "code": meal_code,
            "label": meal_label,
            "time": MEAL_TIMES.get(meal_code),
            "categories": categories,
        })

    return meal_blocks

def required_keys_and_meals(meal_blocks):
    """
    Определяем:
    - required_keys: какие radio-поля обязательны (где есть выборные блюда is_common=False)
    - required_meals: какие meal_code вообще требуют заказа (есть хотя бы один is_common=False)
    """
    required_keys = set()
    required_meals = set()

    for meal in meal_blocks:
        meal_code = meal["code"]
        for cat in meal["categories"]:
            if any(not it.is_common for it in cat["items"]):
                required_keys.add(cat["key"])
                required_meals.add(meal_code)

    return required_keys, required_meals


def orders_items_count_map_for_date(target_date: date, guests_qs):
    """
    Карта: (guest_id, meal_time) -> количество позиций в заказе (OrderItem).
    Если заказ есть, но items=0 — считаем как 0 (то есть меню не выбрано).
    """
    m = {}
    rows = (
        Order.objects
        .filter(date=target_date, guest__in=guests_qs)
        .values("guest_id", "meal_time")
        .annotate(cnt=Count("items"))
    )
    for r in rows:
        m[(r["guest_id"], r["meal_time"])] = int(r["cnt"] or 0)
    return m

def get_cycle_and_day_for_date(target_date: date):
    """
    Возвращает (cycle, day_index) для заданной даты.

    Логика:
    - есть несколько циклов MenuCycle (обычно 2: Меню №1 и Меню №2), days_count = 7;
    - считаем, какой это номер недели от BASE_MENU_CYCLE_DATE;
    - по чётности недели выбираем нужный цикл;
    - day_index = день недели (1 - понедельник, 7 - воскресенье).

    Если в базе всего один MenuCycle — используем его, как раньше.
    """
    cycles = list(MenuCycle.objects.order_by("id"))
    if not cycles:
        return None, None

    # день недели 1..7
    day_index = target_date.weekday() + 1

    cfg = get_menu_rotation_config()

    # Если диетсестра принудительно выбрала цикл — всегда используем его
    if cfg.forced_cycle_id:
        cycle = cfg.forced_cycle
        if cycle and cycle.days_count and day_index > cycle.days_count:
            day_index = cycle.days_count
        return cycle, day_index

    # иначе — автоматическое чередование от cfg.base_date
    base_date = cfg.base_date
    days_diff = (target_date - base_date).days
    week_index = days_diff // 7
    cycle = cycles[week_index % len(cycles)]

    if cycle.days_count and day_index > cycle.days_count:
        day_index = cycle.days_count

    return cycle, day_index

    # Если циклов 2 и более — чередуем по неделям
    days_diff = (target_date - BASE_MENU_CYCLE_DATE).days
    week_index = days_diff // 7  # номер недели от базы (может быть отрицательным)

    cycle_index = week_index % len(cycles)
    cycle = cycles[cycle_index]

    if cycle.days_count and day_index > cycle.days_count:
        day_index = cycle.days_count

    return cycle, day_index

def generate_access_code(length: int = 4) -> str:
    """Простой генератор цифрового кода доступа."""
    digits = string.digits
    return "".join(random.choice(digits) for _ in range(length))


def generate_unique_access_code(length: int = 4) -> str:
    """Генератор кода, который не повторяется среди текущих гостей."""
    while True:
        code = generate_access_code(length)
        if not Guest.objects.filter(access_code=code).exists():
            return code


def cleanup_departed_guests():
    """Удаляем гостей, у которых дата выезда уже прошла."""
    today = timezone.localdate()

    departed = Guest.objects.filter(end_date__lt=today)
    if departed.exists():
        departed.delete()   # каскадно удалит и SeatAssignment
    # ничего не возвращаем, функция просто чистит данные

def guest_required(view_func):
    """Простой декоратор: проверяет, что в сессии есть авторизованный гость."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        guest_id = request.session.get("guest_id")
        if not guest_id:
            return redirect("landing")
        try:
            guest = Guest.objects.get(id=guest_id)
        except Guest.DoesNotExist:
            request.session.pop("guest_id", None)
            return redirect("landing")
        request.guest = guest
        return view_func(request, *args, **kwargs)
    return _wrapped


def ensure_menu_cycles_exist():
    """Убедиться, что есть два 7-дневных меню: Меню №1 и Меню №2."""
    if MenuCycle.objects.count() == 0:
        MenuCycle.objects.bulk_create(
            [
                MenuCycle(name="Меню №1", days_count=7),
                MenuCycle(name="Меню №2", days_count=7),
            ]
        )
    
def get_active_menu_target(now: datetime):
    """
    Возвращает (target_date, window_start, window_end) или (None, None, None),
    где:
      target_date  — дата, на которую сейчас можно выбирать меню (C),
      window_start — начало окна выбора (C-2 17:00),
      window_end   — конец окна выбора (C-1 11:00).

    Окно для дня С: [C-2 17:00; C-1 11:00).
    now должен быть timezone-aware (лучше передавать timezone.localtime()).
    """
    # если вдруг пришёл naive datetime — приводим к текущему TZ
    tz = timezone.get_current_timezone()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, tz)

    today = now.date()

    for delta in range(1, 5):
        target = today + timedelta(days=delta)

        start_naive = datetime.combine(target - timedelta(days=2), time(17, 0))
        end_naive = datetime.combine(target - timedelta(days=1), time(11, 0))

        window_start = timezone.make_aware(start_naive, tz)
        window_end = timezone.make_aware(end_naive, tz)

        if window_start <= now < window_end:
            return target, window_start, window_end

    return None, None, None

@login_required
def diet_home_view(request):
    """
    Кабинет диетсестры.
    """
    cleanup_departed_guests()
    ensure_menu_cycles_exist()
    return render(request, "dining/home.html")

@login_required
def seating_overview_view(request):
    """
    Обзор рассадки на выбранную дату:
    показывает какие столы заняты/свободны.
    """
    cleanup_departed_guests()

    target_date = timezone.localdate()  

    # Все посадки, актуальные на дату
    seats = (
        SeatAssignment.objects
        .filter(start_date__lte=target_date, end_date__gte=target_date)
        .select_related("table", "guest")
    )

    # table_number -> set(places)
    occupied = {}
    for s in seats:
        occupied.setdefault(s.table.number, set()).add(s.place_number)

    total_tables = 100
    places_per_table = 4
    total_places = total_tables * places_per_table

    occupied_places = sum(len(p) for p in occupied.values())
    free_places = total_places - occupied_places

    free_tables = sum(1 for n in range(1, 101) if len(occupied.get(n, set())) == 0)

    # Готовим список столов 1..100
    tables = []
    for n in range(1, 101):
        places = occupied.get(n, set())
        count = len(places)
        if count == 0:
            status = "free"
            status_text = "Свободен"
        elif count < 4:
            status = "partial"
            status_text = f"Занято {count}/4"
        else:
            status = "full"
            status_text = "Занят"

        tables.append({
            "number": n,
            "status": status,
            "status_text": status_text,
        })

    return render(request, "dining/seating_overview.html", {
        "target_date": target_date,
        "tables": tables,
        "total_places": total_places,
        "free_places": free_places,
        "free_tables": free_tables,
    })


@login_required
@transaction.atomic
def table_detail_view(request, table_number: int):
    """
    Детальная страница стола: кто на каких местах на выбранную дату
    + возможность добавить отдыхающего сразу на этот стол.
    """
    cleanup_departed_guests()

    target_date = timezone.localdate()  # ВСЕГДА сегодня


    table = DiningTable.objects.filter(number=table_number).first()

    seats = (
        SeatAssignment.objects
        .filter(table__number=table_number, start_date__lte=target_date, end_date__gte=target_date)
        .select_related("guest", "table")
    )

    place_map = {s.place_number: s.guest for s in seats}
    free_places = [p for p in range(1, 5) if p not in place_map]

    # POST: добавить нового отдыхающего на свободное место
    if request.method == "POST" and request.POST.get("action") == "add_guest":
        form = AddGuestAtTableForm(
            request.POST,
            free_places=free_places,
            start_date=target_date,
        )

        if form.is_valid():
            full_name = form.cleaned_data["full_name"]
            end_date = form.cleaned_data["end_date"]
            diet_kind = form.cleaned_data["diet_kind"]
            place_number = int(form.cleaned_data["place_number"])

            # пересчёт, чтобы не посадить на занятое (на случай гонки)
            if SeatAssignment.objects.filter(
                table__number=table_number,
                place_number=place_number,
                start_date__lte=end_date,
                end_date__gte=target_date,
            ).exists():
                form.add_error(None, "Это место уже занято на выбранную дату.")
            else:
                # создаём стол если его нет
                if not table:
                    table = DiningTable.objects.create(number=table_number, places_count=4)

                access_code = generate_unique_access_code(4)

                guest = Guest.objects.create(
                    full_name=full_name,
                    start_date=target_date,
                    end_date=end_date,
                    access_code=access_code,
                    diet_kind=diet_kind,
                    # Приёмы пищи
                    breakfast_allowed=True,
                    lunch_allowed=True,
                    snack_allowed=False,
                    dinner_allowed=True,
                    # Платный выезд
                    departure_lunch=form.cleaned_data.get("departure_lunch", False),
                    departure_dinner=form.cleaned_data.get("departure_dinner", False),
                )

                SeatAssignment.objects.create(
                    guest=guest,
                    table=table,
                    place_number=place_number,
                    start_date=target_date,
                    end_date=end_date,
                )

                messages.success(request, f"Отдыхающий добавлен. Код доступа: {access_code}")
                return redirect(reverse('table_detail', args=[table_number]))

        # если не валидно — покажем ошибки внизу
        add_form = form
    else:
        add_form = AddGuestAtTableForm(
            free_places=free_places,
            start_date=target_date,
        )

    places = []
    for place_no in range(1, 5):
        g = place_map.get(place_no)
        places.append({"place": place_no, "guest": g})

    return render(request, "dining/table_detail.html", {
        "target_date": target_date,
        "table_number": table_number,
        "table": table,
        "places": places,
        "free_places": free_places,
        "add_form": add_form,
    })

def landing_view(request):
    """
    Главная страница:
    - ссылка для входа сотрудника (диетсестра/официант) по логину/паролю,
    - форма входа отдыхающего по коду.
    """
    cleanup_departed_guests()
    ensure_menu_cycles_exist()

    now = timezone.localtime()
    #now = datetime.combine(date.today(), time(10, 0)) 
    menu_target_date, window_start, window_end = get_active_menu_target(now)
    menu_available = menu_target_date is not None

    error = None
    if request.method == "POST":
        form = GuestLoginForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["access_code"]
            today = date.today()
            try:
                guest = Guest.objects.get(access_code=code, end_date__gte=today)
            except Guest.DoesNotExist:
                error = "Неверный код или срок пребывания уже закончился."
            else:
                request.session["guest_id"] = guest.id
                return redirect("guest_menu")
    else:
        form = GuestLoginForm()

    return render(
        request,
        "dining/landing.html",
        {
            "form": form,
            "error": error,
            "menu_available": menu_available,
            "menu_target_date": menu_target_date,
        },
    )


@login_required
@transaction.atomic
def add_guest_view(request):
    """
    Страница для диетсестры:
    - ввод ФИО, ДАТЫ ВЫЕЗДА, стола и места
    - создание гостя, посадки и кода доступа
    """
    cleanup_departed_guests()   # перед каждой операцией освобождаем уехавших

    if request.method == "POST":
        form = AddGuestForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data["full_name"]
            end_date = form.cleaned_data["end_date"]
            diet_kind = form.cleaned_data["diet_kind"]
            table_number = form.cleaned_data["table_number"]
            place_number = form.cleaned_data["place_number"]

            today = date.today()
            start_date = today
            
            # ищем или создаём стол
            table, _ = DiningTable.objects.get_or_create(
                number=table_number,
                defaults={"places_count": 4},
            )

            # проверяем, не занято ли место в эти даты
            overlap_exists = SeatAssignment.objects.filter(
                table=table,
                place_number=place_number,
                end_date__gte=start_date,
                start_date__lte=end_date,
            ).exists()

            if overlap_exists:
                form.add_error(
                    None,
                    f"Стол №{table_number}, место {place_number} уже занято в этот период.",
                )
            else:
                access_code = generate_unique_access_code(4)

                guest = Guest.objects.create(
                    full_name=full_name,
                    start_date=start_date,
                    end_date=end_date,
                    access_code=access_code,
                    diet_kind=diet_kind,
                    # Приёмы пищи
                    breakfast_allowed=form.cleaned_data.get("breakfast_allowed", True),
                    lunch_allowed=form.cleaned_data.get("lunch_allowed", True),
                    snack_allowed=False,  # скрыто
                    dinner_allowed=form.cleaned_data.get("dinner_allowed", True),
                    # Платный выезд
                    departure_lunch=form.cleaned_data.get("departure_lunch", False),
                    departure_dinner=form.cleaned_data.get("departure_dinner", False),
                )

                SeatAssignment.objects.create(
                    guest=guest,
                    table=table,
                    place_number=place_number,
                    start_date=start_date,
                    end_date=end_date,
                )

                return render(
                    request,
                    "dining/guest_created.html",
                    {
                        "guest": guest,
                        "table": table,
                        "place_numbe    r": place_number,
                    },
                )
    else:
        form = AddGuestForm()

    return render(request, "dining/add_guest.html", {"form": form})

# ---------- Справочник блюд ----------


@login_required
def dish_list_view(request):
    """
    Справочник блюд с поиском по названию.
    """
    q = (request.GET.get("q") or "").strip()

    dishes_qs = Dish.objects.all()

    if q:
        # Поиск без учёта регистра (для кириллицы в SQLite — через разные варианты)
        q_clean = q.lower()
        dishes_qs = dishes_qs.filter(
            Q(name__contains=q_clean) |
            Q(name__contains=q_clean.capitalize()) |
            Q(name__contains=q_clean.upper())
        )

    dishes_qs = dishes_qs.order_by("name")
    count = dishes_qs.count()

    return render(
        request,
        "dining/dish_list.html",
        {
            "dishes": list(dishes_qs),
            "q": q,
            "count": count,
        },
    )

@login_required
def dish_create_view(request):
    if request.method == "POST":
        form = DishForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("dish_list")
    else:
        form = DishForm()
    return render(request, "dining/dish_form.html", {"form": form, "dish": None})



# ---------- Меню на день ----------

@login_required
def daily_menu_select_view(request):
    """
    Выбор меню по КАЛЕНДАРНОЙ ДАТЕ:
    - диетсестра выбирает дату и вид диеты (П/Б/БД),
    - система автоматически определяет Меню №1/№2 и день недели,
    - открывает/создаёт соответствующий DailyMenu (шаблон) и переводит на редактирование.
    """
    ensure_menu_cycles_exist()

    # выбранная дата (для отображения в форме и подсказках)
    date_str = request.GET.get("date")
    if date_str:
        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    cycle, day_index = get_cycle_and_day_for_date(selected_date)

    if request.method == "POST":
        form = DailyMenuSelectForm(request.POST)
        if form.is_valid():
            selected_date = form.cleaned_data["date"]
            diet_kind = form.cleaned_data["diet_kind"]

            cycle, day_index = get_cycle_and_day_for_date(selected_date)
            if not cycle:
                return render(request, "dining/daily_menu_select.html", {
                    "form": form,
                    "selected_date": selected_date,
                    "cycle": None,
                    "day_index": None,
                    "error": "Не найдено меню (MenuCycle). Создайте Меню №1 и Меню №2.",
                })

            daily_menu, _ = DailyMenu.objects.get_or_create(
                cycle=cycle,
                day_index=day_index,
                diet_kind=diet_kind,
            )
            return redirect("daily_menu_edit", menu_id=daily_menu.id)
    else:
        form = DailyMenuSelectForm(initial={
            "date": selected_date,
            "diet_kind": "B",
        })

    return render(request, "dining/daily_menu_select.html", {
        "form": form,
        "selected_date": selected_date,
        "cycle": cycle,
        "day_index": day_index,
        "error": None,
    })

@login_required
def daily_menu_edit_view(request, menu_id: int):
    """
    Редактирование конкретного дня меню:
    - просмотр уже добавленных блюд,
    - редактирование строк,
    - перемещение строк вверх/вниз внутри своего раздела,
    - добавление новых строк (в конец раздела).
    """
    daily_menu = get_object_or_404(DailyMenu, id=menu_id)
    # сортируем приёмы пищи в порядке: завтрак, обед, полдник, ужин
    meal_order = {code: idx for idx, (code, _label) in enumerate(MEAL_CHOICES)}
    items_qs = daily_menu.items.select_related("dish").all()
    items = sorted(
        items_qs,
        key=lambda i: (meal_order.get(i.meal_time, 99), i.order_index, -i.id),
    )

    dishes = Dish.objects.all().order_by("name")
    meal_choices = MEAL_CHOICES

    if request.method == "POST":
        action = request.POST.get("action", "update")

        if action in ("update", "move_up", "move_down"):
            item_id = request.POST.get("item_id")
            item = get_object_or_404(MenuItem, id=item_id, daily_menu=daily_menu)

            if action == "update":
                meal_time = request.POST.get("meal_time") or item.meal_time
                category = request.POST.get("category", "")
                dish_id = request.POST.get("dish_id")
                is_common = bool(request.POST.get("is_common"))

                item.meal_time = meal_time
                item.category = category
                if dish_id:
                    item.dish = get_object_or_404(Dish, id=dish_id)
                item.is_common = is_common
                item.save()

            else:
                # перемещение вверх/вниз внутри того же приёма пищи и раздела
                same_group = MenuItem.objects.filter(
                    daily_menu=daily_menu,
                    meal_time=item.meal_time,
                    category=item.category,
                ).order_by("order_index", "id")

                same_list = list(same_group)
                idx = same_list.index(item)

                if action == "move_up" and idx > 0:
                    neighbor = same_list[idx - 1]
                elif action == "move_down" and idx < len(same_list) - 1:
                    neighbor = same_list[idx + 1]
                else:
                    neighbor = None

                if neighbor:
                    # меняем местами order_index
                    item.order_index, neighbor.order_index = (
                        neighbor.order_index,
                        item.order_index,
                    )
                    item.save()
                    neighbor.save()

            return redirect("daily_menu_edit", menu_id=daily_menu.id)

        else:
            # добавление новой строки
            form = MenuItemForm(request.POST)
            if form.is_valid():
                meal_time = form.cleaned_data["meal_time"]
                category = form.cleaned_data["category"]
                dish = form.cleaned_data["dish"]
                is_common = form.cleaned_data["is_common"]

                # вычисляем следующий порядок в конце своего раздела
                last = (
                    MenuItem.objects.filter(
                        daily_menu=daily_menu,
                        meal_time=meal_time,
                        category=category,
                    )
                    .order_by("-order_index")
                    .first()
                )
                next_order = (last.order_index if last else 0) + 1

                MenuItem.objects.create(
                    daily_menu=daily_menu,
                    meal_time=meal_time,
                    category=category,
                    dish=dish,
                    order_index=next_order,
                    is_common=is_common,
                )
                return redirect("daily_menu_edit", menu_id=daily_menu.id)
    else:
        form = MenuItemForm()

    return render(
        request,
        "dining/daily_menu_edit.html",
        {
            "daily_menu": daily_menu,
            "items": items,
            "form": form,
            "dishes": dishes,
            "meal_choices": meal_choices,
        },
    )

@login_required
def dish_edit_view(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id)
    if request.method == "POST":
        form = DishForm(request.POST, instance=dish)
        if form.is_valid():
            form.save()
            return redirect("dish_list")
    else:
        form = DishForm(instance=dish)
    return render(request, "dining/dish_form.html", {"form": form, "dish": dish})

from django.db.models import Count  # вверху файла, рядом с Q

# ...

@login_required
@transaction.atomic
def dish_delete_view(request, dish_id):
    """
    Удаление блюда из справочника.

    Удаляем:
      - все OrderItem, которые ссылаются на позиции меню с этим блюдом;
      - все MenuItem с этим блюдом;
      - само блюдо;
      - дополнительно чистим заказы без позиций (Order с 0 items).

    ВНИМАНИЕ: после этого блюда не будет ни в текущем меню, ни в
    уже сделанных заказах (история по этому блюду исчезнет).
    """
    dish = get_object_or_404(Dish, id=dish_id)

    if request.method == "POST":
        name = dish.name

        # 1) Удаляем все позиции заказов с этим блюдом
        OrderItem.objects.filter(menu_item__dish=dish).delete()

        # 2) Удаляем все позиции меню с этим блюдом
        MenuItem.objects.filter(dish=dish).delete()

        # 3) Удаляем само блюдо
        dish.delete()

        # 4) Чистим заказы, в которых не осталось ни одной позиции
        Order.objects.annotate(cnt=Count("items")).filter(cnt=0).delete()

        messages.success(
            request,
            f"Блюдо «{name}» и все его позиции в меню/заказах удалены."
        )
        return redirect("dish_list")

    return render(request, "dining/dish_confirm_delete.html", {"dish": dish})

@login_required
def menu_item_delete_view(request, item_id: int):
    item = get_object_or_404(MenuItem, id=item_id)
    menu_id = item.daily_menu_id
    item.delete()
    return redirect("daily_menu_edit", menu_id=menu_id)

@guest_required
def guest_menu_view(request):
    guest = request.guest
    seat = guest.seat_assignments.order_by("-start_date").first()

    now = timezone.localtime()

    # Определяем, для какой даты сейчас можно выбирать меню
    target_date, window_start, window_end = get_active_menu_target(now)
    is_last_day = (target_date is not None and guest.end_date == target_date)

    if not target_date:
        # нет активного окна выбора вообще
        return render(
            request,
            "dining/guest_menu.html",
            {
                "guest": guest,
                "seat": seat,
                "target_date": None,
                "cutoff_date": None,
                "can_edit": False,
                "stay_ended": False,
                "no_window": True,
                "daily_menu": None,
                "meal_blocks": [],
            },
        )

    # Нельзя выбирать меню на дату позже окончания пребывания
    if target_date > guest.end_date:
        return render(
            request,
            "dining/guest_menu.html",
            {
                "guest": guest,
                "seat": seat,
                "target_date": target_date,
                "cutoff_date": window_end.date(),
                "can_edit": False,
                "stay_ended": True,
                "no_window": False,
                "daily_menu": None,
                "meal_blocks": [],
            },
        )

    cutoff_date = window_end.date()
    can_edit = True  # если мы здесь, мы внутри окна выбора

    # Определяем цикл и день цикла для target_date
    cycle, day_index = get_cycle_and_day_for_date(target_date)
    daily_menu = None
    if cycle:
        qs = DailyMenu.objects.filter(cycle=cycle, day_index=day_index)
        if qs.filter(diet_kind=guest.diet_kind).exists():
            daily_menu = qs.filter(diet_kind=guest.diet_kind).first()
        else:
            daily_menu = qs.first()

    if not daily_menu:
        return render(
            request,
            "dining/guest_menu.html",
            {
                "guest": guest,
                "seat": seat,
                "target_date": target_date,
                "cutoff_date": cutoff_date,
                "can_edit": can_edit,
                "stay_ended": False,
                "no_window": False,
                "daily_menu": None,
                "meal_blocks": [],
            },
        )

    # --- Группируем позиции меню по приёмам пищи и разделам ---
    items_by_meal = {code: {} for code, _ in MEAL_CHOICES}
    for item in daily_menu.items.select_related("dish"):
        if item.meal_time not in items_by_meal:
            continue  # старые snack и т.п.
        meal_dict = items_by_meal[item.meal_time]
        category = item.category or ""
        if category not in meal_dict:
            meal_dict[category] = []
        meal_dict[category].append(item)

    # --- Уже сохранённый выбор гостя на эту дату ---
    existing_orders = (
        Order.objects.filter(guest=guest, date=target_date)
        .prefetch_related("items__menu_item")
    )
    selected_by_mealcat = {}
    for order in existing_orders:
        for oi in order.items.all():
            cat = oi.menu_item.category or ""
            selected_by_mealcat[(order.meal_time, cat)] = oi.menu_item_id

    # --- Определяем, какие приёмы разрешены и их подписи ---
    meal_time_labels = {
        "breakfast": "завтрак",
        "lunch": "обед",
        "dinner": "ужин",
    }

    if is_last_day:
        # День выезда: завтрак + платный обед/ужин (если куплены)
        allowed_meal_times = []
        if guest.breakfast_allowed:
            allowed_meal_times.append("breakfast")
        if guest.departure_lunch:
            allowed_meal_times.append("lunch")
        if guest.departure_dinner:
            allowed_meal_times.append("dinner")
    else:
        # Обычные дни
        allowed_meal_times = []
        if guest.breakfast_allowed:
            allowed_meal_times.append("breakfast")
        if guest.lunch_allowed:
            allowed_meal_times.append("lunch")
        if guest.dinner_allowed:
            allowed_meal_times.append("dinner")

    form_error = None  # текст ошибки валидации выбора

    # --- POST: сохраняем ВЕСЬ ДЕНЬ ---
    if request.method == "POST":
        if not can_edit:
            return redirect("guest_menu")

        # Для каждого приёма пищи проверим, есть ли вообще выборные блюда
        has_choice_for_meal = {}
        for meal_code, _label in MEAL_CHOICES:
            meal_categories = items_by_meal.get(meal_code, {})
            has_choice_for_meal[meal_code] = any(
                any(not it.is_common for it in items)
                for items in meal_categories.values()
            )

        per_meal_selected_ids: dict[str, list[int]] = {}
        validation_errors = []

        for meal_code, _label in MEAL_CHOICES:
            meal_categories = items_by_meal.get(meal_code, {})
            selected_ids: list[int] = []

            # порядок категорий должен совпадать с тем, как мы их рисуем
            for idx, (category, items) in enumerate(
                sorted(meal_categories.items(), key=lambda kv: category_sort_key(kv[0]))
            ):
                field_name = f"{meal_code}_cat_{idx}"
                value = request.POST.get(field_name)
                if not value:
                    continue
                try:
                    mid = int(value)
                except ValueError:
                    continue
                if any(it.id == mid for it in items):
                    selected_ids.append(mid)

            per_meal_selected_ids[meal_code] = selected_ids

            # Валидация: если приём пищи разрешён и в нём есть выборные блюда,
            # то нужно выбрать хотя бы одно блюдо.
            if (
                meal_code in allowed_meal_times
                and has_choice_for_meal.get(meal_code)
                and not selected_ids
            ):
                validation_errors.append(
                    f"Выберите хотя бы одно блюдо на {meal_time_labels.get(meal_code, meal_code)}."
                )

        if validation_errors:
            # Не сохраняем, просто показываем ошибку
            form_error = " ".join(validation_errors)
        else:
            # Сохраняем выбор
            for meal_code, _label in MEAL_CHOICES:
                selected_ids = per_meal_selected_ids.get(meal_code, [])
                if selected_ids:
                    order, _ = Order.objects.get_or_create(
                        guest=guest,
                        date=target_date,
                        meal_time=meal_code,
                    )
                    order.items.all().delete()
                    OrderItem.objects.bulk_create(
                        [OrderItem(order=order, menu_item_id=mid) for mid in selected_ids]
                    )
                else:
                    Order.objects.filter(
                        guest=guest,
                        date=target_date,
                        meal_time=meal_code,
                    ).delete()

            # Автоматический выход гостя после сохранения
            request.session.pop("guest_id", None)
            return redirect("landing")

    # --- Структура для шаблона ---

    allowed_meals_display = [
        meal_time_labels[code].capitalize() for code in allowed_meal_times
    ]
    if is_last_day and not allowed_meals_display:
        allowed_meals_display = ["Завтрак"]

    meal_blocks = []
    for code, label in MEAL_CHOICES:
        # Пропускаем запрещённые приёмы пищи
        if code not in allowed_meal_times:
            continue

        meal_categories = items_by_meal.get(code, {})
        if not meal_categories:
            continue

        category_blocks = []
        # сортируем разделы (НАПИТКИ, ЗАКУСКИ, 1-е, 2-е, ДОПОЛНИТЕЛЬНО)
        for idx, (category, items) in enumerate(
            sorted(meal_categories.items(), key=lambda kv: category_sort_key(kv[0]))
        ):
            field_name = f"{code}_cat_{idx}"
            selected_id = selected_by_mealcat.get((code, category))
            category_blocks.append(
                {
                    "key": field_name,
                    "category": category,
                    "items": items,
                    "selected_id": selected_id,
                    # есть ли в этом разделе выборные (не is_common) блюда
                    "has_choices": any(not it.is_common for it in items),
                }
            )

        if category_blocks:
            meal_blocks.append(
                {
                    "code": code,
                    "label": label,
                    "time": MEAL_TIMES.get(code),
                    "categories": category_blocks,
                }
            )

    return render(
        request,
        "dining/guest_menu.html",
        {
            "guest": guest,
            "seat": seat,
            "target_date": target_date,
            "cutoff_date": cutoff_date,
            "can_edit": can_edit,
            "stay_ended": False,
            "is_last_day_menu": (target_date == guest.end_date),
            "daily_menu": daily_menu,
            "meal_blocks": meal_blocks,
            "allowed_meals_display": allowed_meals_display,
            "form_error": form_error,
        },
    )
@login_required
def waiter_overview_view(request):
    """
    Экран официанта:
    - по дате и приёму пищи показывает, какие блюда нести на какие столы/места;
    - можно фильтровать по блюду и по официанту (диапазон столов).
    """
    cleanup_departed_guests()

    today = date.today()
    default_date = today + timedelta(days=1)

    date_str = request.GET.get("date") or default_date.isoformat()
    allowed_meals = [code for code, _ in MEAL_CHOICES]
    if meal_time not in allowed_meals:
        meal_time = allowed_meals[0]
    dish_param = request.GET.get("dish") or ""
    waiter_str = request.GET.get("waiter") or ""

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        selected_date = default_date

    waiter_num = None
    if waiter_str:
        try:
            waiter_num = int(waiter_str)
        except ValueError:
            waiter_num = None

    orders = (
        Order.objects.filter(date=selected_date, meal_time=meal_time)
        .select_related("guest")
        .prefetch_related("items__menu_item__dish", "guest__seat_assignments__table")
    )

    table_map: dict[int, dict[int, list]] = {}  # стол -> место -> [Dish,...]
    all_dishes_set = set()

    dish_filter_id = None
    if dish_param:
        try:
            dish_filter_id = int(dish_param)
        except ValueError:
            dish_filter_id = None

    for order in orders:
        guest = order.guest

        # ищем актуальное место за столом на эту дату
        seat = None
        for s in guest.seat_assignments.all():
            if s.start_date <= selected_date <= s.end_date:
                seat = s
                break
        if not seat:
            continue

        dishes = [oi.menu_item.dish for oi in order.items.all()]
        if not dishes:
            continue

        for d in dishes:
            all_dishes_set.add(d)

        # фильтрация по конкретному блюду (если выбрана)
        if dish_filter_id is not None:
            dishes = [d for d in dishes if d.id == dish_filter_id]
            if not dishes:
                continue

        table_no = seat.table.number
        place_no = seat.place_number

        table_entry = table_map.setdefault(table_no, {})
        place_entry = table_entry.setdefault(place_no, [])
        place_entry.extend(dishes)

    # фильтр по официанту (диапазон столов)
    if waiter_num in WAITER_RANGES:
        start, end = WAITER_RANGES[waiter_num]
        table_map = {
            t: places for t, places in table_map.items()
            if start <= t <= end
        }

    dish_choices = sorted(all_dishes_set, key=lambda d: d.name)
    meal_label = dict(MEAL_CHOICES).get(meal_time, "")

    context = {
        "selected_date": selected_date,
        "selected_date_str": selected_date.isoformat(),
        "meal_time": meal_time,
        "meal_label": meal_label,
        "meal_choices": MEAL_CHOICES,
        "dish_choices": dish_choices,
        "selected_dish_id": dish_filter_id,
        "tables": dict(sorted(table_map.items())),
        "waiter_num": waiter_num,
        "waiter_ranges": WAITER_RANGES,
    }
    return render(request, "dining/waiter_overview.html", context)

@login_required
def waiter_print_compact_view(request):
    """
    Печать для официантов:
    Структура: ПРИЁМ ПИЩИ -> РАЗДЕЛ (Категория) -> БЛЮДО (короткое имя) -> ИТОГО -> СТОЛЫ
    """
    cleanup_departed_guests()

    today = date.today()
    default_date = today + timedelta(days=1)

    date_str = request.GET.get("date") or default_date.isoformat()
    waiter_str = request.GET.get("waiter") or ""
    table_from_str = request.GET.get("table_from") or ""
    table_to_str = request.GET.get("table_to") or ""

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        selected_date = default_date

    waiter_num = None
    if waiter_str:
        try:
            waiter_num = int(waiter_str)
        except ValueError:
            waiter_num = None

    # Фильтр по столам
    if waiter_num in WAITER_RANGES:
        table_from, table_to = WAITER_RANGES[waiter_num]
    else:
        try:
            table_from = int(table_from_str) if table_from_str else 1
        except ValueError:
            table_from = 1
        try:
            table_to = int(table_to_str) if table_to_str else MAX_TABLE_NUMBER
        except ValueError:
            table_to = MAX_TABLE_NUMBER

    table_from = max(1, table_from)
    table_to = min(MAX_TABLE_NUMBER, table_to)

    # 1. Получаем все заказы
    orders = (
        Order.objects.filter(date=selected_date)
        .select_related("guest")
        .prefetch_related(
            "items__menu_item__dish", 
            "guest__seat_assignments__table"
        )
    )

    # 2. Структура для агрегации:
    # aggregated[meal_code][category_name][dish_id] = {
    #    'dish': dish_obj,
    #    'order_index': int (для сортировки внутри категории),
    #    'total': int,
    #    'tables': { table_num: [place_num, ...] }
    # }
    aggregated = {code: {} for code, _ in MEAL_CHOICES}

    # Вспомогательный словарь для порядка категорий: { (meal, category): min_id }
    # Мы будем сортировать категории по тому, как рано они встречаются в базе (приблизительно)
    # или можно просто по алфавиту. Попробуем сохранять порядок добавления.
    
    for order in orders:
        guest = order.guest
        
        # Определяем стол
        seat = None
        for s in guest.seat_assignments.all():
            if s.start_date <= selected_date <= s.end_date:
                seat = s
                break
        if not seat:
            continue

        table_no = seat.table.number
        place_no = seat.place_number

        # Фильтр столов
        if not (table_from <= table_no <= table_to):
            continue

        meal_dict = aggregated.setdefault(order.meal_time, {})

        for oi in order.items.all():
            dish = oi.menu_item.dish
            # Категория из MenuItem. Если нет - "Разное"
            cat_name = oi.menu_item.category.strip() if oi.menu_item.category else "—"
            
            cat_dict = meal_dict.setdefault(cat_name, {})
            
            dish_entry = cat_dict.setdefault(dish.id, {
                "dish": dish,
                "order_index": oi.menu_item.order_index, # сохраняем порядок из меню
                "total": 0,
                "tables": {}
            })

            table_places = dish_entry["tables"].setdefault(table_no, set())
            
            # Увеличиваем счетчик, только если это место еще не посчитано для этого блюда
            # (защита от дублей, если вдруг в базе сбой, хотя unique protect)
            if place_no not in table_places:
                table_places.add(place_no)
                dish_entry["total"] += 1

    # 3. Преобразуем в список для шаблона
    # meal_blocks = [ { 'meal_label': ..., 'categories': [ { 'name': ..., 'dishes': [...] } ] } ]
    
    meal_blocks = []
    
    # Порядок категорий: ЗАКУСКИ, 1-е, 2-е... 
    # Эвристика: сортируем категории по минимальному order_index входящих в них блюд
    
    for code, label in MEAL_CHOICES:
        cats_data = aggregated.get(code, {})
        if not cats_data:
            continue

        # Сортируем категории. 
        # Чтобы "ЗАКУСКИ" были раньше "2-е БЛЮДА", найдем минимальный order_index в каждой категории
        def get_cat_sort_key(cat_item):
            name, dishes_map = cat_item
            # берем минимальный order_index среди блюд этой категории
            if not dishes_map: return 999
            return min(d['order_index'] for d in dishes_map.values())

        sorted_cats = sorted(cats_data.items(), key=get_cat_sort_key)
        
        categories_list = []
        for cat_name, dishes_map in sorted_cats:
            # Сортируем блюда внутри категории (по order_index, затем по имени)
            sorted_dishes = sorted(
                dishes_map.values(),
                key=lambda x: (x["order_index"], x["dish"].name)
            )

            # Список полных названий (со скобками) для поиска общего префикса
            full_names = [entry["dish"].name for entry in sorted_dishes]
            prefix = common_word_prefix(full_names)

            rows = []
            for entry in sorted_dishes:
                dish = entry["dish"]
                base_name = dish.name  # показываем полное название, включая скобки

                if prefix and base_name.startswith(prefix):
                    # Отрезаем общий префикс
                    display_name = base_name[len(prefix):].lstrip()
                    # убираем ведущую запятую, если она сразу после префикса
                    if display_name.startswith(","):
                        display_name = display_name[1:].lstrip()
                else:
                    display_name = base_name

                # Формируем строку столов: "1(1,2); 5(3)"
                tables_data = []
                for t_no in sorted(entry["tables"].keys()):
                    places = sorted(entry["tables"][t_no])
                    places_str = ",".join(str(p) for p in places)
                    tables_data.append({
                        "number": t_no,
                        "formatted": f"{t_no}({places_str})",
                    })

                rows.append({
                    "dish_name": display_name,
                    "total": entry["total"],
                    "tables_data": tables_data,
                    "tables_str": "; ".join([t["formatted"] for t in tables_data]),
                })

            categories_list.append({
                "name": cat_name,
                "rows": rows,
            })

        meal_blocks.append({
            "meal_code": code,
            "meal_label": label,
            "categories": categories_list,
        })

    return render(
        request,
        "dining/waiter_print_compact.html",
        {
            "selected_date": selected_date,
            "waiter_num": waiter_num,
            "waiter_ranges": WAITER_RANGES,
            "table_from": table_from,
            "table_to": table_to,
            "meal_blocks": meal_blocks,
        },
    )
    """
    Компактная печать для официантов:
    ПРИЁМ ПИЩИ -> БЛЮДО -> КОЛ-ВО -> СТОЛЫ(места)

    Формат: Суп — 3 — 50(1,2,3); 72(1,4)
    """
    cleanup_departed_guests()

    today = date.today()
    default_date = today + timedelta(days=1)

    date_str = request.GET.get("date") or default_date.isoformat()
    waiter_str = request.GET.get("waiter") or ""
    table_from_str = request.GET.get("table_from") or ""
    table_to_str = request.GET.get("table_to") or ""

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        selected_date = default_date

    waiter_num = None
    if waiter_str:
        try:
            waiter_num = int(waiter_str)
        except ValueError:
            waiter_num = None

    # диапазон столов
    if waiter_num in WAITER_RANGES:
        table_from, table_to = WAITER_RANGES[waiter_num]
    else:
        try:
            table_from = int(table_from_str) if table_from_str else 1
        except ValueError:
            table_from = 1
        try:
            table_to = int(table_to_str) if table_to_str else MAX_TABLE_NUMBER
        except ValueError:
            table_to = MAX_TABLE_NUMBER

    table_from = max(1, table_from)
    table_to = min(MAX_TABLE_NUMBER, table_to)

    orders = (
        Order.objects.filter(date=selected_date)
        .select_related("guest")
        .prefetch_related("items__menu_item__dish", "guest__seat_assignments__table")
    )

    # meal_map[meal_time][dish_id] = {
    #   "dish": Dish,
    #   "total": int,
    #   "tables": {table_no: set(places)}
    # }
    meal_map: dict[str, dict[int, dict]] = {code: {} for code, _ in MEAL_CHOICES}

    for order in orders:
        guest = order.guest

        # посадка на дату
        seat = None
        for s in guest.seat_assignments.all():
            if s.start_date <= selected_date <= s.end_date:
                seat = s
                break
        if not seat:
            continue

        table_no = seat.table.number
        place_no = seat.place_number

        # фильтр по диапазону столов
        if not (table_from <= table_no <= table_to):
            continue

        for oi in order.items.all():
            dish = oi.menu_item.dish
            meal_dict = meal_map.setdefault(order.meal_time, {})

            entry = meal_dict.setdefault(
                dish.id,
                {"dish": dish, "total": 0, "tables": {}}
            )
            table_places = entry["tables"].setdefault(table_no, set())

            # увеличиваем total только если место для этого блюда в этом столе ещё не учтено
            if place_no not in table_places:
                table_places.add(place_no)
                entry["total"] += 1

    # готовим блоки для шаблона в порядке MEAL_CHOICES
    meal_blocks = []
    for code, label in MEAL_CHOICES:
        dishes = meal_map.get(code, {})
        if not dishes:
            continue

        rows = []
        for dish_id, entry in sorted(dishes.items(), key=lambda x: x[1]["dish"].name):
            table_parts = []
            for t_no in sorted(entry["tables"].keys()):
                places = sorted(entry["tables"][t_no])
                places_str = ",".join(str(p) for p in places)
                # Собираем данные о столах в список словарей
            tables_data = []
            for t_no in sorted(entry["tables"].keys()):
                places = sorted(entry["tables"][t_no])
                places_str = ",".join(str(p) for p in places)
                tables_data.append({
                    "number": t_no,
                    "places": places,
                    "formatted": f"{t_no}({places_str})"
                })

            rows.append({
                "dish_name": entry["dish"].name,
                "total": entry["total"],
                "tables_data": tables_data,  # Передаем структурированные данные
                "tables_str": "; ".join([t["formatted"] for t in tables_data]),  # Оставляем для совместимости
            })

        meal_blocks.append({
            "meal_code": code,
            "meal_label": label,
            "rows": rows,
        })

    return render(
        request,
        "dining/waiter_print_compact.html",
        {
            "selected_date": selected_date,
            "waiter_num": waiter_num,
            "waiter_ranges": WAITER_RANGES,
            "table_from": table_from,
            "table_to": table_to,
            "meal_blocks": meal_blocks,
        },
    )

@login_required
def kitchen_summary_view(request):
    """
    Отчёт для кухни:
    - по выбранной дате показывает, сколько порций каждого блюда заказано,
      с разбивкой по приёмам пищи и по столам.
    """
    cleanup_departed_guests()

    today = date.today()
    default_date = today + timedelta(days=1)  # по умолчанию — завтра

    date_str = request.GET.get("date") or default_date.isoformat()
    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        selected_date = default_date

    # Берём все заказы на эту дату
    orders = (
        Order.objects.filter(date=selected_date)
        .exclude(meal_time="snack")
        .select_related("guest")
        .prefetch_related("items__menu_item__dish", "guest__seat_assignments__table")
    )

    # dish_map[dish_id] = {
    #   "dish": Dish,
    #   "total": int,
    #   "by_meal": {meal_time: int},
    #   "tables": set(table_numbers),
    # }
    dish_map: dict[int, dict] = {}
    all_tables_set = set()

    for order in orders:
        guest = order.guest

        # ищем актуальную посадку гостя на эту дату
        seat = None
        for s in guest.seat_assignments.all():
            if s.start_date <= selected_date <= s.end_date:
                seat = s
                break
        if not seat:
            continue

        table_no = seat.table.number
        all_tables_set.add(table_no)

        meal_time = order.meal_time

        # все блюда в этом заказе
        for oi in order.items.all():
            dish = oi.menu_item.dish
            entry = dish_map.setdefault(
                dish.id,
                {
                    "dish": dish,
                    "total": 0,
                    "by_meal": {code: 0 for code, _ in MEAL_CHOICES},
                    "tables": set(),
                },
            )
            entry["total"] += 1
            entry["by_meal"][meal_time] += 1
            entry["tables"].add(table_no)

    # приводим к списку для шаблона
    meal_labels = dict(MEAL_CHOICES)
    dishes_summary = []

    for dish_id, entry in dish_map.items():
        dishes_summary.append(
            {
                "dish": entry["dish"],
                "total": entry["total"],
                "by_meal": entry["by_meal"],
                "tables": sorted(entry["tables"]),
            }
        )

    # сортировка блюд по названию
    dishes_summary.sort(key=lambda x: x["dish"].name)

    all_tables = sorted(all_tables_set)

    context = {
        "selected_date": selected_date,
        "dishes_summary": dishes_summary,
        "all_tables": all_tables,
        "meal_choices": MEAL_CHOICES,
        "meal_labels": meal_labels,
    }
    return render(request, "dining/kitchen_summary.html", context)

@login_required
def missing_menu_fill_view(request, diet_kind: str):
    """
    Диетсестра выбирает блюда и назначает их всем гостям,
    которые НЕ выбрали меню на дату, для конкретного вида диеты (P/B/BD).

    КРИТИЧНОЕ ИЗМЕНЕНИЕ:
    - в день выезда назначаем ТОЛЬКО те приёмы, которые разрешены (departure_*),
      и не считаем отсутствующие запрещённые приёмы как "не выбрал".
    - не удаляем все заказы гостя на дату: дополняем только недостающие meal_time.
    """
    cleanup_departed_guests()

    diet_labels = dict(DIET_TYPE_CHOICES)
    if diet_kind not in diet_labels:
        return redirect("missing_menu")

    date_str = request.GET.get("date")
    if not date_str:
        return redirect("missing_menu")
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return redirect("missing_menu")

    active_guests = (
        Guest.objects.filter(
            diet_kind=diet_kind,
            start_date__lte=target_date,
            end_date__gte=target_date,
        )
    )

    daily_menu = get_daily_menu_for_date_and_diet(target_date, diet_kind)
    if not daily_menu:
        return render(request, "dining/missing_menu_fill.html", {
            "target_date": target_date,
            "diet_kind": diet_kind,
            "diet_label": diet_labels.get(diet_kind, diet_kind),
            "missing_count": 0,
            "daily_menu": None,
            "meal_blocks": [],
            "error": "На эту дату нет настроенного меню для выбранного вида диеты.",
        })

    meal_blocks = build_meal_blocks_from_daily_menu(daily_menu)
    required_keys, required_meals = required_keys_and_meals(meal_blocks)

    # карта заказов: (guest_id, meal_time) -> count(OrderItem)
    orders_map = orders_items_count_map_for_date(target_date, active_guests)

    # кто "не выбрал" (по разрешённым и требующим выбора приёмам)
    missing_guests = []
    for g in active_guests:
        allowed = allowed_meals_for_guest_on_date(g, target_date)

        # если нет выборных блюд — нечего назначать
        if not required_meals:
            continue

        is_missing = False
        for meal_code in required_meals:
            if not allowed.get(meal_code, False):
                continue
            if orders_map.get((g.id, meal_code), 0) <= 0:
                is_missing = True
                break

        if is_missing:
            missing_guests.append(g)

    missing_count = len(missing_guests)

    if request.method == "POST":
        if missing_count == 0:
            messages.warning(request, "Нет отдыхающих без выбора на эту дату.")
            return redirect(f"{reverse('missing_menu')}?date={target_date.isoformat()}")

        # 1) Валидация: если категория имеет выборные блюда — выбор обязателен
        for k in required_keys:
            if not request.POST.get(k):
                return render(request, "dining/missing_menu_fill.html", {
                    "target_date": target_date,
                    "diet_kind": diet_kind,
                    "diet_label": diet_labels.get(diet_kind, diet_kind),
                    "missing_count": missing_count,
                    "daily_menu": daily_menu,
                    "meal_blocks": meal_blocks,
                    "error": "Выберите блюда во всех разделах (где есть выбор).",
                })

        # 2) Соберём выбранные menu_item_id по приёмам пищи
        selected_by_meal = {code: [] for code, _ in MEAL_CHOICES}

        valid_for_key = {}
        for meal in meal_blocks:
            for cat in meal["categories"]:
                ids = [it.id for it in cat["items"] if not it.is_common]  # общие нельзя выбирать
                valid_for_key[cat["key"]] = set(ids)

        for meal in meal_blocks:
            meal_code = meal["code"]
            for cat in meal["categories"]:
                key = cat["key"]
                val = request.POST.get(key)
                if not val:
                    continue
                try:
                    mid = int(val)
                except ValueError:
                    continue
                if mid in valid_for_key.get(key, set()):
                    selected_by_meal[meal_code].append(mid)

        # если вообще ничего не выбрали — не делаем
        if not any(selected_by_meal.values()):
            messages.warning(request, "Вы не выбрали ни одного блюда. Ничего не назначено.")
            return redirect(request.path + f"?date={target_date.isoformat()}")

        # 3) Применяем ко всем, кто "не выбрал"
        for g in missing_guests:
            allowed = allowed_meals_for_guest_on_date(g, target_date)

            for meal_code in required_meals:
                if not allowed.get(meal_code, False):
                    # в день выезда многие meal_time запрещены — пропускаем
                    continue

                ids = selected_by_meal.get(meal_code) or []
                if not ids:
                    continue

                # если у гостя уже есть выбор по этому meal_time — не трогаем
                if orders_map.get((g.id, meal_code), 0) > 0:
                    continue

                order, _ = Order.objects.get_or_create(
                    guest=g,
                    date=target_date,
                    meal_time=meal_code,
                )
                order.items.all().delete()
                OrderItem.objects.bulk_create(
                    [OrderItem(order=order, menu_item_id=mid) for mid in ids]
                )

        messages.success(
            request,
            f"Назначено выбранное меню для {missing_count} чел. "
            f"({diet_labels.get(diet_kind)}) на {target_date.strftime('%d.%m.%Y')}.",
        )
        return redirect(f"{reverse('missing_menu')}?date={target_date.isoformat()}")

    return render(request, "dining/missing_menu_fill.html", {
        "target_date": target_date,
        "diet_kind": diet_kind,
        "diet_label": diet_labels.get(diet_kind, diet_kind),
        "missing_count": missing_count,
        "daily_menu": daily_menu,
        "meal_blocks": meal_blocks,
        "error": None,
    })

    """
    Диетсестра выбирает блюда из меню на дату и назначает их всем гостям,
    которые НЕ выбрали меню на эту дату, для конкретного вида диеты (P/B/BD).
    """
    cleanup_departed_guests()

    diet_labels = dict(DIET_TYPE_CHOICES)
    if diet_kind not in diet_labels:
        return redirect("missing_menu")

    # дата из query string
    date_str = request.GET.get("date")
    if not date_str:
        return redirect("missing_menu")
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return redirect("missing_menu")

    # список активных гостей этой диеты на дату
    active_guests = Guest.objects.filter(
        diet_kind=diet_kind,
        start_date__lte=target_date,
        end_date__gte=target_date,
    )

    # гости, у кого уже есть заказы на эту дату
    guests_with_orders = set(
        Order.objects.filter(date=target_date).values_list("guest_id", flat=True)
    )

    # те, кто не выбрал
    missing_guests = list(active_guests.exclude(id__in=guests_with_orders))
    missing_count = len(missing_guests)

    # определяем цикл/день недели для этой даты
    cycle, day_index = get_cycle_and_day_for_date(target_date)
    daily_menu = None
    if cycle:
        daily_menu = DailyMenu.objects.filter(
            cycle=cycle,
            day_index=day_index,
            diet_kind=diet_kind,
        ).first()

    if not daily_menu:
        # меню не настроено
        return render(request, "dining/missing_menu_fill.html", {
            "target_date": target_date,
            "diet_kind": diet_kind,
            "diet_label": diet_labels.get(diet_kind, diet_kind),
            "missing_count": missing_count,
            "daily_menu": None,
            "meal_blocks": [],
            "error": "На эту дату нет настроенного меню для выбранного вида диеты.",
        })

    # строим структуру: meal -> categories -> items
    # category_blocks: [{"key": "...", "category": "...", "items": [MenuItem...]}]
    meal_blocks = []
    for meal_code, meal_label in MEAL_CHOICES:
        items = list(
            daily_menu.items.filter(meal_time=meal_code).select_related("dish").order_by("order_index", "id")
        )
        if not items:
            continue

        # группируем по category, сохраняя порядок появления
        cat_map = {}
        for it in items:
            cat = it.category or ""
            cat_map.setdefault(cat, []).append(it)

        categories = []
        idx = 0
        for cat_name, cat_items in cat_map.items():
            # ключ поля для формы
            key = f"{meal_code}_cat_{idx}"
            idx += 1
            categories.append({
                "key": key,
                "category": cat_name,
                "items": cat_items,
            })

        meal_blocks.append({
            "code": meal_code,
            "label": meal_label,
            "time": MEAL_TIMES.get(meal_code),
            "categories": categories,
        })

    # POST: назначаем выбранные блюда всем missing_guests
    if request.method == "POST":
        if missing_count == 0:
            messages.warning(request, "Нет отдыхающих без выбора на эту дату.")
            return redirect(f"{reverse('missing_menu')}?date={target_date.isoformat()}")

        # соберём выбранные menu_item_id по приёмам пищи
        selected_by_meal = {code: [] for code, _ in MEAL_CHOICES}

        # для валидации подготовим допустимые id для каждого поля
        valid_for_key = {}
        for meal in meal_blocks:
            for cat in meal["categories"]:
                ids = [it.id for it in cat["items"] if not it.is_common]  # общие нельзя выбирать
                valid_for_key[cat["key"]] = set(ids)

        for meal in meal_blocks:
            meal_code = meal["code"]
            for cat in meal["categories"]:
                key = cat["key"]
                val = request.POST.get(key)
                if not val:
                    continue
                try:
                    mid = int(val)
                except ValueError:
                    continue
                if mid in valid_for_key.get(key, set()):
                    selected_by_meal[meal_code].append(mid)

        # если вообще ничего не выбрали — не делаем
        if not any(selected_by_meal.values()):
            messages.warning(request, "Вы не выбрали ни одного блюда. Ничего не назначено.")
            return redirect(request.path + f"?date={target_date.isoformat()}")

        # применяем ко всем гостям без выбора
        for g in missing_guests:
            # на всякий случай чистим любые заказы на эту дату (хотя они missing)
            Order.objects.filter(guest=g, date=target_date).delete()

            for meal_code, ids in selected_by_meal.items():
                if not ids:
                    continue
                order = Order.objects.create(
                    guest=g,
                    date=target_date,
                    meal_time=meal_code,
                )
                OrderItem.objects.bulk_create(
                    [OrderItem(order=order, menu_item_id=mid) for mid in ids]
                )

        messages.success(
            request,
            f"Назначено выбранное меню для {missing_count} чел. "
            f"({diet_labels.get(diet_kind)}) на {target_date.strftime('%d.%m.%Y')}.",
        )
        return redirect(f"{reverse('missing_menu')}?date={target_date.isoformat()}")

    return render(request, "dining/missing_menu_fill.html", {
        "target_date": target_date,
        "diet_kind": diet_kind,
        "diet_label": diet_labels.get(diet_kind, diet_kind),
        "missing_count": missing_count,
        "daily_menu": daily_menu,
        "meal_blocks": meal_blocks,
        "error": None,
    })

@login_required
def missing_menu_view(request):
    """
    Страница для диетсестры:
    - показывает, кто НЕ выбрал меню на выбранную дату.

    КРИТИЧНОЕ ИЗМЕНЕНИЕ:
    - в день выезда гость может иметь право только на завтрак или на платный обед/ужин;
      отсутствие "запрещённых" приёмов НЕ считается "не выбрал меню".
    - считаем "не выбрал" только для тех meal_time, которые:
        (а) разрешены гостю на эту дату
        (б) имеют в меню выборные блюда (is_common=False)
    """
    cleanup_departed_guests()
    now = timezone.localtime()

    # дата из query string
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = now.date()
    else:
        # пробуем использовать "активное" меню, иначе завтра
        t_date, _, _ = get_active_menu_target(now)
        target_date = t_date if t_date is not None else now.date() + timedelta(days=1)

    # активные гости на дату (берём сразу с посадками, чтобы меньше запросов)
    active_guests = (
        Guest.objects.filter(start_date__lte=target_date, end_date__gte=target_date)
        .prefetch_related("seat_assignments__table")
    )

    # карта заказов: (guest_id, meal_time) -> count(OrderItem)
    orders_map = orders_items_count_map_for_date(target_date, active_guests)

    # для каждой диеты: какие приёмы пищи реально "требуют выбора" (есть is_common=False)
    required_meals_by_diet = {}
    for diet_code, _label in DIET_TYPE_CHOICES:
        dm = get_daily_menu_for_date_and_diet(target_date, diet_code)
        if not dm:
            required_meals_by_diet[diet_code] = set()
            continue
        meal_blocks = build_meal_blocks_from_daily_menu(dm)
        _required_keys, required_meals = required_keys_and_meals(meal_blocks)
        required_meals_by_diet[diet_code] = required_meals

    # считаем список "не выбрали"
    missing_guests = []
    for g in active_guests:
        allowed = allowed_meals_for_guest_on_date(g, target_date)
        required_meals = required_meals_by_diet.get(g.diet_kind, set())

        # если на эту диету/дату нет выборных блюд — нечего выбирать => не считаем missing
        if not required_meals:
            continue

        is_missing = False
        for meal_code in required_meals:
            if not allowed.get(meal_code, False):
                continue
            if orders_map.get((g.id, meal_code), 0) <= 0:
                is_missing = True
                break

        if is_missing:
            missing_guests.append(g)

    # группируем missing по виду диеты
    by_diet = {code: [] for code, _ in DIET_TYPE_CHOICES}
    for g in missing_guests:
        by_diet.setdefault(g.diet_kind, []).append(g)

    # POST: автоматическое назначение стандартного меню (первое не-общее блюдо по meal_time),
    # но только для разрешённых приёмов пищи и только для тех meal_time, где есть выборные блюда.
    if request.method == "POST":
        diet_to_fill = request.POST.get("diet_kind")  # 'P' / 'B' / 'BD' / 'all'

        if diet_to_fill == "all":
            diets = [code for code, _ in DIET_TYPE_CHOICES]
        else:
            diets = [diet_to_fill] if diet_to_fill else []

        filled_guest_ids = set()

        for diet_code in diets:
            guests_for_diet = by_diet.get(diet_code) or []
            if not guests_for_diet:
                continue

            dm = get_daily_menu_for_date_and_diet(target_date, diet_code)
            if not dm:
                continue

            meal_blocks = build_meal_blocks_from_daily_menu(dm)
            _required_keys, required_meals = required_keys_and_meals(meal_blocks)
            if not required_meals:
                continue

            # "стандартные" блюда: первое не-общее блюдо на каждый приём пищи
            default_item_by_meal = {}
            for meal_code in required_meals:
                first_item = (
                    dm.items
                    .filter(meal_time=meal_code, is_common=False)
                    .order_by("order_index", "id")
                    .first()
                )
                if first_item:
                    default_item_by_meal[meal_code] = first_item

            for guest in guests_for_diet:
                allowed = allowed_meals_for_guest_on_date(guest, target_date)

                any_created = False
                for meal_code in required_meals:
                    if not allowed.get(meal_code, False):
                        continue

                    default_item = default_item_by_meal.get(meal_code)
                    if not default_item:
                        continue

                    # если уже есть выбор (items_count > 0) — не трогаем
                    if orders_map.get((guest.id, meal_code), 0) > 0:
                        continue

                    order, _ = Order.objects.get_or_create(
                        guest=guest,
                        date=target_date,
                        meal_time=meal_code,
                    )
                    order.items.all().delete()
                    OrderItem.objects.create(order=order, menu_item=default_item)
                    any_created = True

                if any_created:
                    filled_guest_ids.add(guest.id)

        if filled_guest_ids:
            messages.success(
                request,
                f"Назначено стандартное меню для {len(filled_guest_ids)} отдыхающих на {target_date.strftime('%d.%m.%Y')}.",
            )
        else:
            messages.warning(
                request,
                "Не удалось назначить меню — возможно, на эту дату нет настроенного дневного меню или нет выборных блюд.",
            )

        return redirect(f"{reverse('missing_menu')}?date={target_date.isoformat()}")

    # статистика и подробный список по диетам
    diet_labels = dict(DIET_TYPE_CHOICES)
    stats = []
    total_missing = 0

    for code, label in DIET_TYPE_CHOICES:
        guests_for_diet = by_diet.get(code) or []
        entries = []

        for g in guests_for_diet:
            # ищем место за столом на эту дату
            seat = None
            for s in g.seat_assignments.all():
                if s.start_date <= target_date <= s.end_date:
                    seat = s
                    break

            entries.append({
                "guest": g,
                "table": seat.table.number if seat else None,
                "place": seat.place_number if seat else None,
            })

        entries.sort(
            key=lambda e: (
                e["table"] if e["table"] is not None else 9999,
                e["place"] if e["place"] is not None else 9999,
                e["guest"].full_name,
            )
        )

        if entries:
            stats.append({
                "code": code,
                "label": diet_labels.get(code, label),
                "count": len(entries),
                "entries": entries,
            })
            total_missing += len(entries)

    return render(request, "dining/missing_menu.html", {
        "target_date": target_date,
        "total_missing": total_missing,
        "stats": stats,
    })


def guest_logout_view(request):
    request.session.pop("guest_id", None)
    return redirect("landing")

@login_required
@transaction.atomic
def move_guest_view(request, guest_id: int):
    cleanup_departed_guests()

    guest = get_object_or_404(Guest, id=guest_id)

    date_str = request.GET.get("date")
    if date_str:
        try:
            move_date = date.fromisoformat(date_str)
        except ValueError:
            move_date = date.today()
    else:
        move_date = date.today()

    # нельзя пересаживать на дату после окончания пребывания
    if move_date > guest.end_date:
        return render(request, "dining/move_guest.html", {
            "guest": guest,
            "move_date": move_date,
            "error": "Нельзя пересаживать на дату позже окончания пребывания.",
            "tables": range(1, 101),
            "places": range(1, 5),
            "current_table": None,
            "current_place": None,
        })

    # находим текущую посадку на эту дату
    current = None
    for s in guest.seat_assignments.all():
        if s.start_date <= move_date <= s.end_date:
            current = s
            break

    current_table = current.table.number if current else None
    current_place = current.place_number if current else None

    if request.method == "POST":
        try:
            new_table_number = int(request.POST.get("table_number"))
            new_place_number = int(request.POST.get("place_number"))
        except (TypeError, ValueError):
            new_table_number = None
            new_place_number = None

        if not new_table_number or new_table_number < 1 or new_table_number > 100:
            error = "Неверный номер стола."
        elif new_place_number < 1 or new_place_number > 4:
            error = "Неверный номер места."
        else:
            error = None

        if error:
            return render(request, "dining/move_guest.html", {
                "guest": guest,
                "move_date": move_date,
                "error": error,
                "tables": range(1, 101),
                "places": range(1, 5),
                "current_table": current_table,
                "current_place": current_place,
                "new_table_number": new_table_number,
                "new_place_number": new_place_number,
            })

        new_table, _ = DiningTable.objects.get_or_create(
            number=new_table_number,
            defaults={"places_count": 4},
        )

        # проверяем, свободно ли место на период [move_date .. guest.end_date]
        conflict = SeatAssignment.objects.filter(
            table=new_table,
            place_number=new_place_number,
            start_date__lte=guest.end_date,
            end_date__gte=move_date,
        ).exclude(guest=guest).exists()

        if conflict:
            return render(request, "dining/move_guest.html", {
                "guest": guest,
                "move_date": move_date,
                "error": f"Стол №{new_table_number}, место {new_place_number} занято в этот период.",
                "tables": range(1, 101),
                "places": range(1, 5),
                "current_table": current_table,
                "current_place": current_place,
                "new_table_number": new_table_number,
                "new_place_number": new_place_number,
            })

        # если текущей посадки нет — просто создаём новую с move_date до end_date
        if not current:
            SeatAssignment.objects.create(
                guest=guest,
                table=new_table,
                place_number=new_place_number,
                start_date=move_date,
                end_date=guest.end_date,
            )
        else:
            # если пересадка с даты начала текущей посадки — просто меняем стол/место
            if current.start_date >= move_date:
                current.table = new_table
                current.place_number = new_place_number
                current.save()
            else:
                # иначе: закрываем старую посадку накануне и создаём новую
                current.end_date = move_date - timedelta(days=1)
                current.save()

                SeatAssignment.objects.create(
                    guest=guest,
                    table=new_table,
                    place_number=new_place_number,
                    start_date=move_date,
                    end_date=guest.end_date,
                )

        return redirect(f"/diet/seating/table/{new_table_number}/?date={move_date.isoformat()}")

    return render(request, "dining/move_guest.html", {
        "guest": guest,
        "move_date": move_date,
        "tables": range(1, 101),
        "places": range(1, 5),
        "current_table": current_table,
        "current_place": current_place,
        "new_table_number": current_table,
        "new_place_number": current_place,
        "error": None,
    })

def get_menu_rotation_config():
    cfg, _ = MenuRotationConfig.objects.get_or_create(id=1)
    return cfg

@login_required
def menu_settings_view(request):
    cfg = get_menu_rotation_config()
    cycles = list(MenuCycle.objects.order_by("id"))

    if request.method == "POST":
        forced = request.POST.get("forced_cycle")  # "" | cycle_id
        base_date_str = request.POST.get("base_date") or ""

        # base_date
        try:
            cfg.base_date = date.fromisoformat(base_date_str) if base_date_str else cfg.base_date
        except ValueError:
            pass

        # forced_cycle
        if forced == "":
            cfg.forced_cycle = None
        else:
            try:
                cid = int(forced)
                cfg.forced_cycle = MenuCycle.objects.filter(id=cid).first()
            except ValueError:
                cfg.forced_cycle = None

        cfg.save()
        messages.success(request, "Настройки меню сохранены.")
        return redirect("menu_settings")

    return render(request, "dining/menu_settings.html", {
        "cfg": cfg,
        "cycles": cycles,
    })

@login_required
def guest_meals_edit_view(request, guest_id: int):
    guest = get_object_or_404(Guest, id=guest_id)

    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = GuestMealsForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            messages.success(request, f"Приёмы пищи обновлены: {guest.full_name}")

            # безопасно возвращаемся назад, если next на наш сайт
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
            ):
                return redirect(next_url)

            return redirect("guest_list")
    else:
        form = GuestMealsForm(instance=guest)

    return render(request, "dining/guest_meals_edit.html", {
        "guest": guest,
        "form": form,
        "next": next_url,
    })

@login_required
def guest_departure_edit_view(request, guest_id: int):
    """
    Изменение даты выезда для отдыхающего.
    Работает аналогично guest_meals_edit_view: есть параметр next для возврата.
    """
    guest = get_object_or_404(Guest, id=guest_id)
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = GuestDepartureForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Дата выезда для «{guest.full_name}» изменена на {guest.end_date:%d.%m.%Y}."
            )

            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)

            return redirect("guest_list")
    else:
        form = GuestDepartureForm(instance=guest)

    return render(
        request,
        "dining/guest_departure_edit.html",
        {
            "guest": guest,
            "form": form,
            "next": next_url,
        },
    )

@login_required
def guest_list_view(request):
    """
    Список отдыхающих с поиском по ФИО.
    Показываем активных на выбранную дату (по умолчанию сегодня).
    """
    cleanup_departed_guests()

    # дата просмотра
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    q = (request.GET.get("q") or "").strip()

    guests_qs = Guest.objects.filter(
        start_date__lte=target_date,
        end_date__gte=target_date,
    )

    if q:
        q_clean = q.lower()
        guests_qs = guests_qs.filter(
            Q(full_name__contains=q_clean) |
            Q(full_name__contains=q_clean.capitalize()) |
            Q(full_name__contains=q_clean.upper())
        )

    guests_qs = guests_qs.order_by("full_name")

    seats = (
        SeatAssignment.objects
        .filter(start_date__lte=target_date, end_date__gte=target_date)
        .select_related("table", "guest")
    )
    seat_by_guest_id = {s.guest_id: s for s in seats}

    guests = []
    for g in guests_qs:
        s = seat_by_guest_id.get(g.id)
        guests.append({
            "guest": g,
            "table": s.table.number if s else None,
            "place": s.place_number if s else None,
        })

    return render(request, "dining/guest_list.html", {
        "target_date": target_date,
        "q": q,
        "guests": guests,
        "count": len(guests),
    })
    """
    Список отдыхающих с поиском по ФИО.
    Показываем активных на выбранную дату (по умолчанию сегодня).
    Диетсестра может менять дату выезда прямо в таблице.
    """
    cleanup_departed_guests()

    # --- POST: изменение даты выезда ---
    if request.method == "POST":
        guest_id = request.POST.get("guest_id")
        new_date_str = request.POST.get("new_end_date") or ""
        orig_date_str = request.POST.get("orig_date") or ""
        orig_q = request.POST.get("orig_q") or ""

        if guest_id and new_date_str:
            try:
                g = Guest.objects.get(id=int(guest_id))
            except (Guest.DoesNotExist, ValueError):
                messages.error(request, "Не удалось найти отдыхающего.")
            else:
                try:
                    new_end = date.fromisoformat(new_date_str)
                except ValueError:
                    messages.error(request, "Некорректная дата выезда.")
                else:
                    if new_end < g.start_date:
                        messages.error(
                            request,
                            f"Дата выезда не может быть раньше даты заезда ({g.start_date:%d.%m.%Y})."
                        )
                    else:
                        g.end_date = new_end
                        g.save(update_fields=["end_date"])
                        messages.success(
                            request,
                            f"Дата выезда для «{g.full_name}» изменена на {new_end:%d.%m.%Y}."
                        )

        # Возвращаемся на список с исходными фильтрами (date, q)
        params = {}
        if orig_date_str:
            params["date"] = orig_date_str
        if orig_q:
            params["q"] = orig_q

        url = reverse("guest_list")
        if params:
            url += "?" + urlencode(params)

        return redirect(url)

    # --- GET: отображение списка ---

    # дата просмотра
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    q = (request.GET.get("q") or "").strip()

    guests_qs = Guest.objects.filter(
        start_date__lte=target_date,
        end_date__gte=target_date,
    )

    if q:
        # Для корректного поиска кириллицы в SQLite без учета регистра
        q_clean = q.lower()
        guests_qs = guests_qs.filter(
            Q(full_name__contains=q_clean) |
            Q(full_name__contains=q_clean.capitalize()) |
            Q(full_name__contains=q_clean.upper())
        )

    guests_qs = guests_qs.order_by("full_name")

    # посадки на эту дату (чтобы показать стол/место)
    seats = (
        SeatAssignment.objects
        .filter(start_date__lte=target_date, end_date__gte=target_date)
        .select_related("table", "guest")
    )
    seat_by_guest_id = {s.guest_id: s for s in seats}

    guests = []
    for g in guests_qs:
        s = seat_by_guest_id.get(g.id)
        guests.append({
            "guest": g,
            "table": s.table.number if s else None,
            "place": s.place_number if s else None,
        })

    return render(request, "dining/guest_list.html", {
        "target_date": target_date,
        "q": q,
        "guests": guests,
        "count": len(guests),
    })
    """
    Список отдыхающих с поиском по ФИО.
    Показываем активных на выбранную дату (по умолчанию сегодня).
    """
    cleanup_departed_guests()

    # дата просмотра
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    q = (request.GET.get("q") or "").strip()

    guests_qs = Guest.objects.filter(
        start_date__lte=target_date,
        end_date__gte=target_date,
    )

    if q:
        # Для корректного поиска кириллицы в SQLite без учета регистра
        # проверяем варианты: "текст", "Текст", "ТЕКСТ"
        q_clean = q.lower()
        guests_qs = guests_qs.filter(
            Q(full_name__contains=q_clean) | 
            Q(full_name__contains=q_clean.capitalize()) | 
            Q(full_name__contains=q_clean.upper())
        )

    guests_qs = guests_qs.order_by("full_name")

    # посадки на эту дату (чтобы показать стол/место)
    seats = (
        SeatAssignment.objects
        .filter(start_date__lte=target_date, end_date__gte=target_date)
        .select_related("table", "guest")
    )
    seat_by_guest_id = {s.guest_id: s for s in seats}

    guests = []
    for g in guests_qs:
        s = seat_by_guest_id.get(g.id)
        guests.append({
            "guest": g,
            "table": s.table.number if s else None,
            "place": s.place_number if s else None,
        })

    return render(request, "dining/guest_list.html", {
        "target_date": target_date,
        "q": q,
        "guests": guests,
        "count": len(guests),
    })