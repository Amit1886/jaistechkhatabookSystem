from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0015_product_min_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="created_at",
            field=models.DateTimeField(default=timezone.now, auto_now_add=True),
            preserve_default=False,
        ),
    ]

