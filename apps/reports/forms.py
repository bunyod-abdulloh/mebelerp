from django import forms
from django.core.exceptions import ValidationError

MAX_PERIOD_DAYS = 366


class PeriodForm(forms.Form):
    date_from = forms.DateField()
    date_to = forms.DateField()

    def clean(self):
        data = super().clean()
        date_from, date_to = data.get("date_from"), data.get("date_to")
        if date_from and date_to:
            if date_from > date_to:
                raise ValidationError("Boshlanish sanasi tugash sanasidan keyin bo'lmasligi kerak.")
            if (date_to - date_from).days > MAX_PERIOD_DAYS:
                raise ValidationError("Davr 1 yildan oshmasligi kerak.")
        return data
