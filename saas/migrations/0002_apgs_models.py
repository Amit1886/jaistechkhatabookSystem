from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("saas", "0001_initial"),
        ("vendors", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=60, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.CreateModel(
            name="PermissionNode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=120, unique=True)),
                ("label", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("module", models.CharField(blank=True, db_index=True, max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="permissions",
                        to="saas.department",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="saas.permissionnode",
                    ),
                ),
            ],
            options={"ordering": ["module", "key"]},
        ),
        migrations.CreateModel(
            name="RoleTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("is_system", models.BooleanField(db_index=True, default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roles",
                        to="saas.department",
                    ),
                ),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.CreateModel(
            name="RoleTemplatePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "effect",
                    models.CharField(
                        choices=[("allow", "Allow"), ("deny", "Deny")],
                        db_index=True,
                        default="allow",
                        max_length=10,
                    ),
                ),
                (
                    "permission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_edges",
                        to="saas.permissionnode",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_edges",
                        to="saas.roletemplate",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="UserPermissionGraph",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inherit_from_owner", models.BooleanField(db_index=True, default=True)),
                ("overrides_json", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_graphs",
                        to="saas.roletemplate",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_permission_graphs",
                        to="vendors.vendor",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_graphs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"indexes": [models.Index(fields=["user", "seller", "is_active"], name="saas_userpe_user_id_5bc5b7_idx")]},
        ),
        migrations.AlterUniqueTogether(name="roletemplatepermission", unique_together={("role", "permission")}),
    ]

