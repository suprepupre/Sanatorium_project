from datetime import date

from django import forms

from .models import Dish, MenuCycle, MEAL_CHOICES, DIET_TYPE_CHOICES, DAY_OF_WEEK_CHOICES

class AddGuestForm(forms.Form):
    full_name = forms.CharField(label="ФИО", max_length=200)

    end_date = forms.DateField(
    label="Дата выезда",
    input_formats=["%Y-%m-%d"],
    widget=forms.DateInput(
        attrs={"class": "js-datepicker"},
        format="%Y-%m-%d",
        ),
    )
    diet_kind = forms.ChoiceField(
        label="Вид диеты",
        choices=DIET_TYPE_CHOICES,
        initial="B",
    )

    table_number = forms.IntegerField(label="Номер стола", min_value=1, max_value=80)
    place_number = forms.IntegerField(label="Номер места", min_value=1, max_value=4)

        # Разрешённые приёмы пищи
    breakfast_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Завтрак"
    )
    lunch_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Обед"
    )
    snack_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Полдник"
    )
    dinner_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Ужин"
    )

    def clean(self):
        cleaned = super().clean()
        end = cleaned.get("end_date")
        today = date.today()

        if end and end < today:
            raise forms.ValidationError("Дата выезда не может быть раньше сегодняшнего дня.")
        return cleaned


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ["name", "is_diet", "proteins", "fats", "carbs", "kcal", "output"]
        labels = {
            "name": "Название",
            "is_diet": "Диетическое блюдо",
            "proteins": "Белки, г",
            "fats": "Жиры, г",
            "carbs": "Углеводы, г",
            "kcal": "Ккал",
            "output": "Выход, г",
        }


class DailyMenuSelectForm(forms.Form):
    date = forms.DateField(
        label="Дата",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={"class": "js-datepicker"},
            format="%Y-%m-%d",
        ),
    )
    diet_kind = forms.ChoiceField(
        label="Вид диеты",
        choices=DIET_TYPE_CHOICES,
    )


class MenuItemForm(forms.Form):
    meal_time = forms.ChoiceField(label="Приём пищи", choices=MEAL_CHOICES)
    category = forms.CharField(
        label="Раздел (например, ЗАКУСКИ)", max_length=50, required=False
    )
    dish = forms.ModelChoiceField(label="Блюдо", queryset=Dish.objects.all())
    is_common = forms.BooleanField(
        label="Общее блюдо (выдаётся всем)", required=False, initial=False
    )


class GuestLoginForm(forms.Form):
    access_code = forms.CharField(label="Код доступа", max_length=10)


from datetime import date
from django import forms
from .models import DIET_TYPE_CHOICES

class AddGuestAtTableForm(forms.Form):
    full_name = forms.CharField(label="ФИО", max_length=200)

    end_date = forms.DateField(
    label="Дата выезда",
    input_formats=["%Y-%m-%d"],
    widget=forms.DateInput(
        attrs={"class": "js-datepicker"},
        format="%Y-%m-%d",
        ),
    )

    diet_kind = forms.ChoiceField(
        label="Вид диеты",
        choices=DIET_TYPE_CHOICES,  # P / B / BD
        initial="B",
    )

    place_number = forms.ChoiceField(
        label="Место",
        choices=[],
    )

        # Разрешённые приёмы пищи
    breakfast_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Завтрак"
    )
    lunch_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Обед"
    )
    snack_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Полдник"
    )
    dinner_allowed = forms.BooleanField(
        required=False,
        initial=True,
        label="Ужин"
    )

    def __init__(self, *args, free_places=None, start_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_date = start_date or date.today()
        free_places = free_places or []
        self.fields["place_number"].choices = [(str(p), str(p)) for p in free_places]

    def clean(self):
        cleaned = super().clean()
        end = cleaned.get("end_date")
        if end and end < self.start_date:
            raise forms.ValidationError("Дата выезда не может быть раньше даты посадки.")
        return cleaned