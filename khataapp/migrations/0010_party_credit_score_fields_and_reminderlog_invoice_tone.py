# Generated manually (no runtime makemigrations available in this environment).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0024_product_image"),
        ("khataapp", "0009_companysettings_auto_sms_send"),
    ]

    operations = [
        migrations.AddField(
            model_name="party",
            name="average_payment_delay",
            field=models.IntegerField(
                default=0,
                help_text="Average payment delay (days). 0 means on-time/early on average.",
            ),
        ),
        migrations.AddField(
            model_name="party",
            name="credit_score",
            field=models.PositiveSmallIntegerField(
                default=50,
                help_text="Smart Khata credit score (0-100). Auto-updated based on payment behavior.",
            ),
        ),
        migrations.AddField(
            model_name="party",
            name="last_payment_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="party",
            name="total_due",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="reminderlog",
            name="invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="khata_reminder_logs",
                to="commerce.invoice",
            ),
        ),
        migrations.AddField(
            model_name="reminderlog",
            name="tone",
            field=models.CharField(
                choices=[("friendly", "Friendly"), ("professional", "Professional"), ("strict", "Strict")],
                default="professional",
                max_length=20,
            ),
        ),
    ]

