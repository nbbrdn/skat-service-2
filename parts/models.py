from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models

class Part(models.Model):
    name = models.CharField("Название", max_length=255)
    price = models.DecimalField("Цена, ₽", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        verbose_name = "Запчасть"
        verbose_name_plural = "Запчасти"
        ordering = ("name", "pk")

    def __str__(self):
        return self.name
