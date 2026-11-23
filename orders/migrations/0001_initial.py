import decimal
import django.db.models.deletion
import django.core.validators
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("parts", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Оформлен")),
                ("total_amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=18, verbose_name="Сумма, ₽")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Заказ", "verbose_name_plural": "Заказы", "ordering": ("-created_at", "-pk")},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("part_name", models.CharField(max_length=255, verbose_name="Название на момент заказа")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Цена на момент заказа, ₽")),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name="Количество")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order", verbose_name="Заказ")),
                ("part", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="parts.part", verbose_name="Запчасть")),
            ],
            options={"verbose_name": "Строка заказа", "verbose_name_plural": "Строки заказа"},
        ),
    ]
