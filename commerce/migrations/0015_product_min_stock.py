from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0014_order_warehouse"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="min_stock",
            field=models.PositiveIntegerField(default=0),
        ),
    ]

