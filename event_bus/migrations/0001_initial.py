from __future__ import annotations

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventOutbox",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("topic", models.CharField(db_index=True, max_length=120)),
                ("event_type", models.CharField(db_index=True, max_length=120)),
                ("key", models.CharField(blank=True, db_index=True, default="", max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="outbox_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "event_outbox",
                "ordering": ["status", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="eventoutbox",
            index=models.Index(fields=["status", "created_at"], name="outbox_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="eventoutbox",
            index=models.Index(fields=["topic", "created_at"], name="outbox_topic_created_idx"),
        ),
    ]

