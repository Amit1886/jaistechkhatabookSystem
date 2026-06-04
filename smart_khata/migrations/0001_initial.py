# Generated manually (no runtime makemigrations available in this environment).
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("khataapp", "0009_companysettings_auto_sms_send"),
        ("commerce", "0024_product_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentBehavior",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("due_date", models.DateField(db_index=True)),
                ("paid_date", models.DateField(blank=True, db_index=True, null=True)),
                ("delay_days", models.IntegerField(db_index=True, default=0, help_text="Paid late by N days (0 = on time/early)")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "customer",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_behaviors",
                        to="khataapp.party",
                    ),
                ),
                (
                    "invoice",
                    models.OneToOneField(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_behavior",
                        to="commerce.invoice",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="smart_khata_payment_behaviors",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["owner", "customer", "-created_at"], name="skb_owner_cust_ca_idx"),
                    models.Index(fields=["owner", "due_date"], name="skb_owner_due_idx"),
                    models.Index(fields=["owner", "delay_days"], name="skb_owner_delay_idx"),
                ],
            },
        ),
    ]

