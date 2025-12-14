from django.urls import path
from . import views

urlpatterns = [
    # Главная (вход)
    path("", views.landing_view, name="landing"),

    # Кабинет диетсестры
    path("diet/home/", views.diet_home_view, name="diet_home"),
    path("add-guest/", views.add_guest_view, name="add_guest"),
    path("diet/seating/", views.seating_overview_view, name="seating_overview"),
    path("diet/seating/table/<int:table_number>/", views.table_detail_view, name="table_detail"),
    path("diet/missing/", views.missing_menu_view, name="missing_menu"),
    path("diet/seating/move/<int:guest_id>/", views.move_guest_view, name="move_guest"),
    path("diet/missing/fill/<str:diet_kind>/", views.missing_menu_fill_view, name="missing_menu_fill"),
    path("diet/menu-settings/", views.menu_settings_view, name="menu_settings"),
    path("diet/guests/", views.guest_list_view, name="guest_list"),


    # Справочник блюд
    path("dishes/", views.dish_list_view, name="dish_list"),
    path("dishes/add/", views.dish_create_view, name="dish_add"),
    path("dishes/<int:dish_id>/edit/", views.dish_edit_view, name="dish_edit"),


    # Меню
    path("menus/select/", views.daily_menu_select_view, name="daily_menu_select"),
    path("menus/<int:menu_id>/edit/", views.daily_menu_edit_view, name="daily_menu_edit"),
    path("menus/item/<int:item_id>/delete/", views.menu_item_delete_view, name="menu_item_delete"),

    # Печатная раскладка официанта (сразу печатная страница)
    
    # станет:
    path("waiter/", views.waiter_print_compact_view, name="waiter_overview"),
    path("waiter/print-compact/", views.waiter_print_compact_view, name="waiter_print_compact"),
    # (опционально) оставить старую печать по столам:
    # path("waiter/print/", views.waiter_print_view, name="waiter_print"),


    # Отчёт для кухни (сразу печатная страница с выбором даты)
    path("kitchen/", views.kitchen_summary_view, name="kitchen_summary"),
    path("kitchen/summary/", views.kitchen_summary_view),  # необязательно

    # Отдыхающие
    path("guest/menu/", views.guest_menu_view, name="guest_menu"),
    path("guest/logout/", views.guest_logout_view, name="guest_logout"),
]