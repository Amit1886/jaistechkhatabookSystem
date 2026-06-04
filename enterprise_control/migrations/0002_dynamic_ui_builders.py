from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("enterprise_control", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DynamicButton",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=90, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                ("action_type", models.CharField(choices=[("route", "Open Route"), ("api", "Call API"), ("module", "Open Module"), ("report", "Open Report"), ("service", "Run Service")], default="route", max_length=20)),
                ("route", models.CharField(blank=True, default="", max_length=180)),
                ("api_endpoint", models.CharField(blank=True, default="", max_length=220)),
                ("service_key", models.CharField(blank=True, default="", max_length=120)),
                ("icon", models.CharField(blank=True, default="bolt", max_length=60)),
                ("color", models.CharField(blank=True, default="#2563EB", max_length=20)),
                ("gradient", models.JSONField(blank=True, default=list)),
                ("shape", models.CharField(choices=[("rounded", "Rounded"), ("square", "Square"), ("pill", "Pill"), ("circle", "Circle")], default="rounded", max_length=20)),
                ("animation", models.CharField(blank=True, default="smooth", max_length=40)),
                ("permission_key", models.CharField(blank=True, default="", max_length=120)),
                ("plan_keys", models.JSONField(blank=True, default=list)),
                ("role_keys", models.JSONField(blank=True, default=list)),
                ("platform_access", models.JSONField(blank=True, default=list)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("order", models.PositiveIntegerField(db_index=True, default=100)),
                ("is_primary", models.BooleanField(db_index=True, default=False)),
                ("is_enabled", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="buttons", to="enterprise_control.dynamicmodule")),
                ("workspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="buttons", to="enterprise_control.workspace")),
            ],
            options={"ordering": ["order", "label"]},
        ),
        migrations.CreateModel(
            name="DynamicMenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(db_index=True, max_length=90, unique=True)),
                ("title", models.CharField(max_length=120)),
                ("icon", models.CharField(blank=True, default="apps", max_length=60)),
                ("route", models.CharField(blank=True, default="", max_length=180)),
                ("badge", models.CharField(blank=True, default="", max_length=40)),
                ("color", models.CharField(blank=True, default="#2563EB", max_length=20)),
                ("permission_key", models.CharField(blank=True, default="", max_length=120)),
                ("platform_access", models.JSONField(blank=True, default=list)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("order", models.PositiveIntegerField(db_index=True, default=100)),
                ("is_group", models.BooleanField(db_index=True, default=False)),
                ("is_enabled", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="menu_items", to="enterprise_control.dynamicmodule")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="enterprise_control.dynamicmenuitem")),
                ("workspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="menu_items", to="enterprise_control.workspace")),
            ],
            options={"ordering": ["order", "title"]},
        ),
        migrations.AddIndex(model_name="dynamicbutton", index=models.Index(fields=["is_enabled", "order"], name="enterprise__is_enab_ba1c8d_idx")),
        migrations.AddIndex(model_name="dynamicmenuitem", index=models.Index(fields=["parent", "is_enabled", "order"], name="enterprise__parent__8f1f3d_idx")),
    ]
