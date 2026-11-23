import decimal
from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(
        name="Part",
        fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=255, verbose_name="Название")),
            ("price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))], verbose_name="Цена, ₽")),
        ],
        options={"verbose_name": "Запчасть", "verbose_name_plural": "Запчасти", "ordering": ("name", "pk")},
    )]
