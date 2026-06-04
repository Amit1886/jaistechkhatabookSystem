from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commerce", "0026_whatsapp_account_links"),
        ("khataapp", "0013_transaction_audit_refs"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("kiosk_id", models.CharField(db_index=True, default="KIOSK-1", max_length=40)),
                ("status", models.CharField(choices=[("active", "Active"), ("payment_pending", "Payment Pending"), ("paid", "Paid"), ("abandoned", "Abandoned"), ("cancelled", "Cancelled")], db_index=True, default="active", max_length=20)),
                ("payment_method", models.CharField(blank=True, default="", max_length=30)),
                ("payment_reference", models.CharField(blank=True, db_index=True, default="", max_length=100)),
                ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("discount_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("tax_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("started_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_activity_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("fraud_flags", models.JSONField(blank=True, default=list)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="self_checkout_sessions", to="khataapp.party")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="self_checkout_sessions", to="commerce.invoice")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-started_at", "-id"]},
        ),
        migrations.CreateModel(
            name="CheckoutCartItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("barcode", models.CharField(blank=True, default="", max_length=80)),
                ("quantity", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=12)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_percent", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=6)),
                ("discount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="self_checkout_items", to="commerce.product")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="selfcheckout.checkoutsession")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddIndex(model_name="checkoutsession", index=models.Index(fields=["owner", "status", "last_activity_at"], name="selfco_owner_status_dt")),
        migrations.AddIndex(model_name="checkoutsession", index=models.Index(fields=["owner", "kiosk_id", "status"], name="selfco_owner_kiosk_status")),
        migrations.AddConstraint(model_name="checkoutcartitem", constraint=models.UniqueConstraint(fields=("session", "product"), name="uniq_selfco_session_product")),
        migrations.AddConstraint(model_name="checkoutcartitem", constraint=models.CheckConstraint(check=models.Q(("quantity__gt", 0)), name="selfco_item_qty_positive")),
    ]
