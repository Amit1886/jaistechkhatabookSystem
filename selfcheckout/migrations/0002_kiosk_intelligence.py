from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("selfcheckout", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="checkoutsession",
            name="ai_context",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="checkoutsession",
            name="applied_coupon",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.CreateModel(
            name="KioskDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kiosk_id", models.CharField(db_index=True, max_length=40, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("zone", models.CharField(blank=True, default="Front Checkout", max_length=80)),
                ("status", models.CharField(choices=[("online", "Online"), ("busy", "Busy"), ("offline", "Offline"), ("maintenance", "Maintenance")], db_index=True, default="online", max_length=20)),
                ("scanner_status", models.CharField(default="online", max_length=20)),
                ("printer_status", models.CharField(default="ready", max_length=20)),
                ("payment_status", models.CharField(default="online", max_length=20)),
                ("internet_status", models.CharField(default="online", max_length=20)),
                ("camera_status", models.CharField(default="ready", max_length=20)),
                ("cpu_usage", models.PositiveSmallIntegerField(default=18)),
                ("memory_usage", models.PositiveSmallIntegerField(default=34)),
                ("avg_checkout_seconds", models.PositiveIntegerField(default=165)),
                ("last_seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("diagnostics", models.JSONField(blank=True, default=dict)),
                ("current_session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_kiosks", to="selfcheckout.checkoutsession")),
            ],
            options={"ordering": ["kiosk_id"]},
        ),
        migrations.CreateModel(
            name="QueueTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ticket_code", models.CharField(db_index=True, max_length=24, unique=True)),
                ("status", models.CharField(choices=[("waiting", "Waiting"), ("assigned", "Assigned"), ("served", "Served"), ("cancelled", "Cancelled")], db_index=True, default="waiting", max_length=20)),
                ("estimated_wait_seconds", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("served_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_kiosk", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_tickets", to="selfcheckout.kioskdevice")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_queue", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="KioskEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("scan", "Scan"), ("rfid", "RFID"), ("voice", "Voice"), ("coupon", "Coupon"), ("payment", "Payment"), ("fraud", "Fraud"), ("health", "Health"), ("assistant", "Assistant")], db_index=True, max_length=20)),
                ("message", models.CharField(blank=True, default="", max_length=255)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("severity", models.CharField(db_index=True, default="info", max_length=20)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("kiosk", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="selfcheckout.kioskdevice")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="events", to="selfcheckout.checkoutsession")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="queueticket",
            index=models.Index(fields=["owner", "status", "created_at"], name="selfco_queue_owner_status"),
        ),
        migrations.AddIndex(
            model_name="kioskevent",
            index=models.Index(fields=["event_type", "created_at"], name="selfco_event_type_dt"),
        ),
    ]
