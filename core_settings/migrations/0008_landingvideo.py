from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_settings", "0007_alter_featuresettings_feature"),
    ]

    operations = [
        migrations.CreateModel(
            name="LandingVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=140)),
                ("video_file", models.FileField(blank=True, null=True, upload_to="landing/videos/")),
                ("video_url", models.URLField(blank=True, default="", help_text="Direct MP4/WebM URL (optional).")),
                ("thumbnail", models.ImageField(blank=True, null=True, upload_to="landing/video_thumbs/")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={
                "verbose_name": "Landing Video",
                "verbose_name_plural": "Landing Videos",
                "ordering": ["sort_order", "-created_at"],
            },
        ),
    ]

