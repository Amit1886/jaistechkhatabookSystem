from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0017_payment_soft_delete"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncQueue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_name", models.CharField(db_index=True, help_text="Django model label (recommended: app_label.ModelName).", max_length=100)),
                ("object_id", models.CharField(db_index=True, help_text="Local primary key value (stored as string for flexibility).", max_length=64)),
                ("action", models.CharField(choices=[("create", "Create"), ("update", "Update"), ("delete", "Delete")], db_index=True, max_length=10)),
                ("synced", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ["synced", "-created_at"],
            },
        ),
    ]

