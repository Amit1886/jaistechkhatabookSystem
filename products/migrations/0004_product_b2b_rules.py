from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_backfill_product_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="moq",
            field=models.PositiveIntegerField(default=1, help_text="Minimum order quantity for B2B."),
        ),
        migrations.AddField(
            model_name="product",
            name="bulk_qty",
            field=models.PositiveIntegerField(default=0, help_text="Bulk tier activates at this quantity (0 disables)."),
        ),
        migrations.AddField(
            model_name="product",
            name="bulk_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Bulk unit price for B2B.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="is_b2b_only",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Hide product for B2C users/guests.",
            ),
        ),
    ]

