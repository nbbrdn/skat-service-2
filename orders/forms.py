from django import forms

MAX_QUANTITY = 999

class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=MAX_QUANTITY)
