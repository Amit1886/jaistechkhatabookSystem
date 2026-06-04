from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0010_marketplaceapp_vendorappinstall"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorShopifyConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shop_domain", models.CharField(blank=True, db_index=True, default="", max_length=120)),
                ("access_token", models.TextField(blank=True, default="")),
                ("scope", models.CharField(blank=True, default="", max_length=600)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("installed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("last_sync_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=255)),
                (
                    "vendor",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shopify_connection",
                        to="vendors.vendor",
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name="vendorshopifyconnection",
            index=models.Index(fields=["shop_domain", "is_active", "updated_at"], name="vendors_ven_shop_do_570e8b_idx"),
        ),
    ]

