from decimal import Decimal

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commerce", "0024_product_image"),
        ("khataapp", "0009_companysettings_auto_sms_send"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplierPriceAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("new_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("change_pct", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=8)),
                ("direction", models.CharField(choices=[("up", "Increase"), ("down", "Decrease")], default="up", max_length=8)),
                ("threshold_pct", models.DecimalField(decimal_places=2, default=Decimal("10.00"), max_digits=8)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_price_alerts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_price_alerts",
                        to="commerce.product",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_alerts",
                        to="khataapp.party",
                    ),
                ),
            ],
            options={
                "verbose_name": "Supplier Price Alert",
                "verbose_name_plural": "Supplier Price Alerts",
                "ordering": ["is_read", "-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["owner", "is_read", "created_at"], name="procurement_owner_i_4d1a75_idx"),
                    models.Index(fields=["owner", "product", "created_at"], name="procurement_owner_p_3f75cb_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SupplierPriceHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("new_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("change_pct", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=8)),
                ("updated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_price_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_price_history",
                        to="commerce.product",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_history",
                        to="khataapp.party",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="supplier_price_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Supplier Price History",
                "verbose_name_plural": "Supplier Price History",
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(fields=["owner", "product", "supplier"], name="procurement_owner_p_093421_idx"),
                    models.Index(fields=["owner", "supplier", "updated_at"], name="procurement_owner_s_2d34a6_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SupplierProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("moq", models.PositiveIntegerField(default=1, verbose_name="Minimum order qty")),
                ("delivery_days", models.PositiveIntegerField(default=1)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_products",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_products",
                        to="commerce.product",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_products",
                        to="khataapp.party",
                    ),
                ),
            ],
            options={
                "verbose_name": "Supplier Product",
                "verbose_name_plural": "Supplier Products",
                "ordering": ["product_id", "supplier_id"],
                "indexes": [
                    models.Index(fields=["owner", "product"], name="procurement_owner_p_eb0186_idx"),
                    models.Index(fields=["owner", "supplier"], name="procurement_owner_s_3f199d_idx"),
                    models.Index(fields=["owner", "product", "supplier"], name="procurement_owner_p_f8f445_idx"),
                ],
                "unique_together": {("owner", "supplier", "product")},
            },
        ),
        migrations.CreateModel(
            name="SupplierRating",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "delivery_speed",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                    ),
                ),
                (
                    "product_quality",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                    ),
                ),
                (
                    "pricing",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)],
                    ),
                ),
                ("comment", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplier_ratings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submitted_supplier_ratings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ratings",
                        to="khataapp.party",
                    ),
                ),
            ],
            options={
                "verbose_name": "Supplier Rating",
                "verbose_name_plural": "Supplier Ratings",
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(fields=["owner", "supplier"], name="procurement_owner_s_66404c_idx"),
                    models.Index(fields=["owner", "rated_by"], name="procurement_owner_r_3ab57c_idx"),
                ],
                "unique_together": {("owner", "supplier", "rated_by")},
            },
        ),
    ]
