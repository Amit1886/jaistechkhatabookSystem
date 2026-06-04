from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0018_syncqueue"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncedInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(db_index=True, max_length=32, unique=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
    ]

