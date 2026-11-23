from django import forms

from .cart import MAX_QUANTITY

class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=MAX_QUANTITY)
