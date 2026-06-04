from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0013_order_bill_sundry"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="commerce.warehouse",
            ),
        ),
    ]

