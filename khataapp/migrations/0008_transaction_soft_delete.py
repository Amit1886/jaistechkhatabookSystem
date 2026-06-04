from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("khataapp", "0007_offlinemessage_recipient_mobile_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="transaction",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

