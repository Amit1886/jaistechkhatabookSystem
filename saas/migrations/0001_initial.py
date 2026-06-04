from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PermissionMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=120, unique=True)),
                ("label", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("module", models.CharField(blank=True, db_index=True, max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"ordering": ["module", "key"]},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("is_system", models.BooleanField(db_index=True, default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="saas.permissionmaster")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="saas.role")),
            ],
        ),
        migrations.AlterUniqueTogether(name="rolepermission", unique_together={("role", "permission")}),
    ]
