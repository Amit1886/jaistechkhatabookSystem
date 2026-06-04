from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_user_saas_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="billing_access_level",
            field=models.CharField(
                blank=True,
                choices=[("admin", "Admin"), ("user", "User")],
                db_index=True,
                default="",
                help_text="Admin/User access layer for billing model hierarchy.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="billing_role_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sub_user", "Sub User"),
                    ("supplier", "Supplier"),
                    ("vendor", "Vendor"),
                    ("customer", "Customer"),
                    ("field_agent", "Field Agent"),
                    ("ai_agent", "AI Agent"),
                ],
                db_index=True,
                default="",
                help_text="Role type within billing hierarchy (sub_user/supplier/vendor/customer/field_agent/ai_agent).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="billing_child_role",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Optional child role within selected billing_role_type (stored as key).",
                max_length=30,
            ),
        ),
    ]

