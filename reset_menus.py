from django.db import transaction

from dining.models import OrderItem, Order, MenuItem, DailyMenu

@transaction.atomic
def main():
    # 1) Сначала удаляем заказы (иначе MenuItem не удалится из-за PROTECT)
    oi = OrderItem.objects.count()
    o = Order.objects.count()
    OrderItem.objects.all().delete()
    Order.objects.all().delete()

    # 2) Потом меню
    mi = MenuItem.objects.count()
    dm = DailyMenu.objects.count()
    MenuItem.objects.all().delete()
    DailyMenu.objects.all().delete()

    print("Удалено OrderItem:", oi)
    print("Удалено Order:", o)
    print("Удалено MenuItem:", mi)
    print("Удалено DailyMenu:", dm)
    print("Готово. Циклы меню и блюда НЕ трогали.")

main()