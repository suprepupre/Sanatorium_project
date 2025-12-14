from django.contrib import admin
from .models import Guest, DiningTable, SeatAssignment, Dish, MenuCycle, DailyMenu, MenuItem

@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "start_date", "end_date", "access_code")
    search_fields = ("full_name", "access_code")

admin.site.register(DiningTable)
admin.site.register(SeatAssignment)
admin.site.register(Dish)
admin.site.register(MenuCycle)
admin.site.register(DailyMenu)
admin.site.register(MenuItem)