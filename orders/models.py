from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="Пользователь")
    created_at = models.DateTimeField("Оформлен", auto_now_add=True)
    total_amount = models.DecimalField("Сумма, ₽", max_digits=18, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"Заказ №{self.pk}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    # FK optional: history survives removal of a catalog entry.
    part = models.ForeignKey("parts.Part", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items", verbose_name="Запчасть")
    part_name = models.CharField("Название на момент заказа", max_length=255)
    unit_price = models.DecimalField("Цена на момент заказа, ₽", max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество", validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "Строка заказа"
        verbose_name_plural = "Строки заказа"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.part_name} × {self.quantity}"
