from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("saas", "0002_apgs_models"),
        ("vendors", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPermissionOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "effect",
                    models.CharField(
                        choices=[("allow", "Allow"), ("deny", "Deny"), ("none", "Inherit")],
                        db_index=True,
                        default="none",
                        max_length=10,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "permission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_overrides",
                        to="saas.permissionnode",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional per-vendor override scope (Phase A tenancy).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_permission_overrides",
                        to="vendors.vendor",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_overrides",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name="userpermissionoverride",
            index=models.Index(fields=["user", "seller", "effect"], name="saas_userpe_user_id_39cf18_idx"),
        ),
        migrations.AlterUniqueTogether(name="userpermissionoverride", unique_together={("user", "seller", "permission")}),
    ]

