from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models

class Part(models.Model):
    name = models.CharField("Название", max_length=255)
    price = models.DecimalField("Цена, ₽", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    external_id = models.UUIDField("GUID 1С", unique=True, null=True, blank=True)
    code = models.CharField("Код 1С", max_length=64, blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Запчасть"
        verbose_name_plural = "Запчасти"
        ordering = ("name", "pk")

    def __str__(self):
        return self.name


class StockBalance(models.Model):
    part = models.OneToOneField(Part, on_delete=models.CASCADE, related_name="stock_balance", verbose_name="Запчасть")
    quantity = models.DecimalField("Остаток", max_digits=18, decimal_places=3, null=True, blank=True)
    source_version = models.BigIntegerField("Версия в источнике", null=True, blank=True)
    source_updated_at = models.DateTimeField("Время снимка в источнике", null=True, blank=True)
    received_at = models.DateTimeField("Время получения", null=True, blank=True)

    class Meta:
        verbose_name = "Остаток запчасти"
        verbose_name_plural = "Остатки запчастей"

    def __str__(self):
        return str(self.part)


class SyncState(models.Model):
    class Kind(models.TextChoices):
        STOCK = "stock", "Остатки запчастей"

    kind = models.CharField("Тип синхронизации", max_length=32, choices=Kind, primary_key=True)
    last_success_at = models.DateTimeField("Последняя успешная синхронизация", null=True, blank=True)

    class Meta:
        verbose_name = "Состояние синхронизации"
        verbose_name_plural = "Состояния синхронизации"

    def __str__(self):
        return self.get_kind_display()
