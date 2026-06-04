from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorStoreSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("support_email", models.EmailField(blank=True, max_length=254)),
                ("support_phone", models.CharField(blank=True, max_length=20)),
                ("address_line1", models.CharField(blank=True, max_length=255)),
                ("address_line2", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("state", models.CharField(blank=True, max_length=80)),
                ("pincode", models.CharField(blank=True, max_length=12)),
                ("country", models.CharField(blank=True, default="India", max_length=80)),
                ("timezone", models.CharField(blank=True, default="Asia/Kolkata", max_length=64)),
                ("currency", models.CharField(blank=True, default="INR", max_length=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "vendor",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_settings",
                        to="vendors.vendor",
                    ),
                ),
            ],
        ),
    ]
