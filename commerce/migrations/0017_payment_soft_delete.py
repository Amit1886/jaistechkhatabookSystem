from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0016_product_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="payment",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

