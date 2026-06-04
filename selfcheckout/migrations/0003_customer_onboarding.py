from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("khataapp", "0013_transaction_audit_refs"),
        ("selfcheckout", "0002_kiosk_intelligence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="checkoutsession",
            name="customer_mode",
            field=models.CharField(db_index=True, default="unidentified", max_length=20),
        ),
        migrations.AddField(
            model_name="checkoutsession",
            name="customer_verified",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="checkoutsession",
            name="customer_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="checkoutsession",
            name="guest_reference",
            field=models.CharField(blank=True, db_index=True, default="", max_length=60),
        ),
        migrations.CreateModel(
            name="CustomerMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("member_code", models.CharField(db_index=True, max_length=32, unique=True)),
                ("qr_token", models.CharField(db_index=True, max_length=80, unique=True)),
                ("nfc_uid", models.CharField(blank=True, db_index=True, max_length=80, null=True, unique=True)),
                ("face_hash", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("tier", models.CharField(db_index=True, default="Silver", max_length=30)),
                ("wallet_balance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("welcome_coupon", models.CharField(blank=True, default="", max_length=40)),
                ("welcome_awarded", models.BooleanField(default=False)),
                ("consent_face", models.BooleanField(default=False)),
                ("is_blocked", models.BooleanField(db_index=True, default=False)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_memberships", to=settings.AUTH_USER_MODEL)),
                ("party", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_membership", to="khataapp.party")),
            ],
            options={"ordering": ["-last_seen_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="CustomerOTPChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mobile", models.CharField(db_index=True, max_length=15)),
                ("purpose", models.CharField(choices=[("existing", "Existing Customer"), ("onboard", "New Customer")], db_index=True, default="existing", max_length=20)),
                ("code", models.CharField(max_length=8)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("is_verified", models.BooleanField(db_index=True, default=False)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_checkout_otps", to=settings.AUTH_USER_MODEL)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otp_challenges", to="selfcheckout.checkoutsession")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="customermembership",
            index=models.Index(fields=["owner", "tier"], name="selfco_mem_owner_tier"),
        ),
        migrations.AddIndex(
            model_name="customermembership",
            index=models.Index(fields=["owner", "is_blocked"], name="selfco_mem_owner_blocked"),
        ),
        migrations.AddIndex(
            model_name="customerotpchallenge",
            index=models.Index(fields=["owner", "mobile", "is_verified"], name="selfco_otp_owner_mobile"),
        ),
    ]
