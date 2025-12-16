from django.db import transaction
from dining.models import OrderItem, Order, MenuItem, DailyMenu, Dish

@transaction.atomic
def main():
    oi = OrderItem.objects.count()
    o = Order.objects.count()
    mi = MenuItem.objects.count()
    dm = DailyMenu.objects.count()
    d = Dish.objects.count()

    OrderItem.objects.all().delete()
    Order.objects.all().delete()
    MenuItem.objects.all().delete()
    DailyMenu.objects.all().delete()
    Dish.objects.all().delete()

    print("Удалено OrderItem:", oi)
    print("Удалено Order:", o)
    print("Удалено MenuItem:", mi)
    print("Удалено DailyMenu:", dm)
    print("Удалено Dish:", d)
    print("Готово.")

main()