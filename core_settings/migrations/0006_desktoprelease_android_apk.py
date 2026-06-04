from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_settings", "0005_desktoprelease"),
    ]

    operations = [
        migrations.AddField(
            model_name="desktoprelease",
            name="android_apk",
            field=models.FileField(blank=True, null=True, upload_to="android_releases/"),
        ),
        migrations.AddField(
            model_name="desktoprelease",
            name="android_sha256",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

