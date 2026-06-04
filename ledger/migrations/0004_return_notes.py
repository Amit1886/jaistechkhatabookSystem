from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0016_product_created_at"),
        ("ledger", "0003_receipt"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReturnNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note_type", models.CharField(choices=[("credit", "Credit Note"), ("debit", "Debit Note")], db_index=True, max_length=10)),
                ("date", models.DateField(db_index=True, default=django.utils.timezone.now)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=20)),
                ("narration", models.TextField(blank=True, default="")),
                ("taxable_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("tax_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("total_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_notes", to="commerce.invoice")),
                ("owner", models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name="return_notes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="ReturnNoteItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=14)),
                ("rate", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("note", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="ledger.returnnote")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_note_items", to="commerce.product")),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="returnnote",
            index=models.Index(fields=["owner", "note_type", "date"], name="idx_rn_owner_type_date"),
        ),
        migrations.AddIndex(
            model_name="returnnote",
            index=models.Index(fields=["owner", "status", "date"], name="idx_rn_owner_status_date"),
        ),
        migrations.AddIndex(
            model_name="returnnoteitem",
            index=models.Index(fields=["note", "product"], name="idx_rni_note_product"),
        ),
    ]

