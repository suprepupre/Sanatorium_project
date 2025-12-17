# merge_dish_duplicates.py
import os
import django
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sanatorium.settings")
django.setup()

from dining.models import Dish, MenuItem  # noqa


# ПАРЫ (keep_id, remove_id)
MERGE_PAIRS = [
    # Группа 61
    (624, 610),  # салат из варёных овощей
    (351, 87),   # суп картофельный с рисом
    (88, 462),   # суп молочный с овощами
    (466, 92),   # кнели из говядины, гречка рассыпчатая
    (105, 470),  # котлеты паровые, перловая каша (batон -> батон)
    (131, 486),  # салат "Белоснежка"

    # Группа 16
    (499, 161),  # котлета "Вясковая", гречневая рассыпчатая
    (523, 394),  # тефтели паровые, картофельное пюре

    # Группа 35
    (260, 455),  # шницель из капусты со сметаной
    (305, 475),  # суп картофельный с фрикадельками
    # (309, 477)  # ПТИЦА С РАЗНЫМИ ОВОЩАМИ — НЕ ТРОГАЕМ, МОЖЕТ БЫТЬ РАЗНЫМ БЛЮДОМ
    (533, 651),  # зразы куриные, овощи отварные
    (332, 493),  # суфле паровое, гречка
    (333, 494),  # салат из печени
    (548, 344),  # омлет с сыром
]


@transaction.atomic
def main():
    for keep_id, remove_id in MERGE_PAIRS:
        try:
            keep = Dish.objects.get(id=keep_id)
        except Dish.DoesNotExist:
            print(f"!! Блюдо id={keep_id} не найдено, пропускаю пару {(keep_id, remove_id)}")
            continue

        try:
            dup = Dish.objects.get(id=remove_id)
        except Dish.DoesNotExist:
            print(f"!! Блюдо id={remove_id} не найдено (возможно, уже удалено), пропускаю.")
            continue

        moved = MenuItem.objects.filter(dish=dup).update(dish=keep)
        print(f"Переназначено {moved} позиций меню с id={remove_id} "
              f"('{dup.name}') на id={keep_id} ('{keep.name}')")

        dup.delete()
        print(f"Удалено блюдо id={remove_id}\n")

    print("Готово.")


if __name__ == "__main__":
    main()