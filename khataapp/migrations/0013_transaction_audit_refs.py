from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("khataapp", "0012_party_pincode_party_pincode_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_khata_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="voucher_type",
            field=models.CharField(blank=True, db_index=True, max_length=40, null=True),
        ),
    ]
