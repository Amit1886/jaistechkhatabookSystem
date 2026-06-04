from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("smart_bi", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FraudAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("invoice_spike", "Invoice Spike"), ("payment_spike", "Payment Spike"), ("rapid_activity", "Rapid Activity")], db_index=True, max_length=40)),
                ("score", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("message", models.CharField(blank=True, default="", max_length=255)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("reference_type", models.CharField(blank=True, db_index=True, default="", max_length=100)),
                ("reference_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("is_resolved", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fraud_alerts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "fraud_alerts",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="fraudalert",
            index=models.Index(fields=["owner", "kind", "-created_at"], name="fraud_owner_kind_dt_idx"),
        ),
    ]
