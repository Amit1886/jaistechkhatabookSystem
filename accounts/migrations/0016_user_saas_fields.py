from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0001_initial"),
        ("accounts", "0015_user_parent_user_referral_code_user_referred_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="store_type",
            field=models.CharField(
                choices=[("b2b", "B2B"), ("b2c", "B2C"), ("hybrid", "Hybrid")],
                db_index=True,
                default="hybrid",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="primary_role",
            field=models.CharField(blank=True, db_index=True, default="", help_text="owner/manager/billing/warehouse/accounts/vendor/staff/custom", max_length=30),
        ),
        migrations.AddField(
            model_name="user",
            name="permissions_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="user",
            name="seller",
            field=models.ForeignKey(
                blank=True,
                help_text="Phase A: link user to Vendor. Phase B: replace with tenant FK.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="seller_users",
                to="vendors.vendor",
            ),
        ),
    ]

