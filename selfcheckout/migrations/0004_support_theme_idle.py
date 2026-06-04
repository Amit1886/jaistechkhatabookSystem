from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("selfcheckout", "0003_customer_onboarding"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_type", models.CharField(db_index=True, default="general_help", max_length=60)),
                ("priority", models.CharField(choices=[("normal", "Normal"), ("urgent", "Urgent"), ("emergency", "Emergency")], db_index=True, default="normal", max_length=20)),
                ("status", models.CharField(choices=[("open", "Open"), ("assigned", "Assigned"), ("resolved", "Resolved"), ("cancelled", "Cancelled")], db_index=True, default="open", max_length=20)),
                ("customer_name", models.CharField(blank=True, default="", max_length=120)),
                ("opened_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_self_checkout_support", to=settings.AUTH_USER_MODEL)),
                ("kiosk", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_requests", to="selfcheckout.kioskdevice")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_support_requests", to=settings.AUTH_USER_MODEL)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_requests", to="selfcheckout.checkoutsession")),
            ],
            options={"ordering": ["-opened_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="supportrequest",
            index=models.Index(fields=["owner", "status", "opened_at"], name="selfco_support_owner_status"),
        ),
        migrations.AddIndex(
            model_name="supportrequest",
            index=models.Index(fields=["kiosk", "status"], name="selfco_support_kiosk_status"),
        ),
    ]
