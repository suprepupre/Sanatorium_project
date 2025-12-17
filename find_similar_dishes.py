# find_similar_dishes.py
import os
import django
import re
from collections import defaultdict

# Настраиваем Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sanatorium.settings")
django.setup()

from dining.models import Dish  # noqa


def normalize_name(name: str) -> str:
    """
    Нормализуем название:
    - убираем всё в круглых скобках (состав блюда),
    - приводим к нижнему регистру,
    - заменяем повторяющиеся пробелы,
    - обрезаем пробелы и запятые по краям.

    Цель — чтобы
      'Кнели из птицы ..., каша гречневая рассып./соус'
    и
      'Кнели из птицы ..., каша гречневая рассыпчатая/соус'
    попали в одну группу.
    """
    s = name

    # убираем содержимое всех скобок "(...)" вместе с пробелом перед ними
    s = re.sub(r"\s*\([^)]*\)", "", s)

    # типовые мелкие расхождения можно немного нормализовать
    # (можно добавлять по мере необходимости)
    replacements = {
        "рассып./": "рассыпчатая/",
        "рассып./соус": "рассыпчатая/соус",
        "рассыпчатая.": "рассыпчатая",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    # убираем лишние пробелы
    s = re.sub(r"\s+", " ", s).strip(" ,;")

    # к нижнему регистру, чтобы "Рыба" и "рыба" были одинаковыми
    s = s.lower()

    return s


def main():
    groups = defaultdict(list)

    for dish in Dish.objects.all():
        key = normalize_name(dish.name)
        groups[key].append(dish)

    # Печатаем только группы, где больше 1 блюда
    similar_groups = [g for g in groups.values() if len(g) > 1]

    if not similar_groups:
        print("Подозрительных дублей не найдено.")
        return

    for idx, group in enumerate(similar_groups, start=1):
        print(f"\n=== Группа {idx} ===")
        for d in group:
            print(f"[id={d.id}] {d.name}")

    print("\nВсего групп с возможными дублями:", len(similar_groups))


if __name__ == "__main__":
    main()