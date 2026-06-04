from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_settings", "0004_alter_settingcategory_id_alter_settingdefinition_id_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DesktopRelease",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.CharField(db_index=True, default="0.0.0", max_length=50)),
                ("windows_exe", models.FileField(blank=True, null=True, upload_to="desktop_releases/")),
                ("sha256", models.CharField(blank=True, default="", max_length=64)),
                ("notes", models.TextField(blank=True, default="")),
                ("is_published", models.BooleanField(db_index=True, default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Desktop Release",
                "verbose_name_plural": "Desktop Releases",
            },
        ),
    ]

