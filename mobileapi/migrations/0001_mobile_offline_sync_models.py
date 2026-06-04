from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MobileCustomer",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=80)),
                ("name", models.CharField(max_length=200)),
                ("phone", models.CharField(blank=True, default="", max_length=40)),
                ("address", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(db_index=True)),
                ("updated_at", models.DateTimeField(db_index=True)),
                ("is_synced", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Mobile Customer",
                "verbose_name_plural": "Mobile Customers",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="MobileProduct",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=80)),
                ("name", models.CharField(max_length=200)),
                ("sku", models.CharField(blank=True, default="", max_length=80)),
                ("price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("tax_percent", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("created_at", models.DateTimeField(db_index=True)),
                ("updated_at", models.DateTimeField(db_index=True)),
                ("is_synced", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Mobile Product",
                "verbose_name_plural": "Mobile Products",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="MobileInvoice",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=80)),
                ("customer_id", models.CharField(db_index=True, max_length=80)),
                ("number", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(db_index=True, default="unpaid", max_length=20)),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("discount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("tax", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("paid", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("balance", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(db_index=True)),
                ("updated_at", models.DateTimeField(db_index=True)),
                ("is_synced", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Mobile Invoice",
                "verbose_name_plural": "Mobile Invoices",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MobileInvoiceItem",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("invoice_id", models.CharField(db_index=True, max_length=80)),
                ("product_id", models.CharField(db_index=True, max_length=80)),
                ("name", models.CharField(max_length=200)),
                ("qty", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("tax_percent", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("line_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(db_index=True)),
                ("updated_at", models.DateTimeField(db_index=True)),
                ("is_synced", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Mobile Invoice Item",
                "verbose_name_plural": "Mobile Invoice Items",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MobilePayment",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("invoice_id", models.CharField(db_index=True, max_length=80)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("mode", models.CharField(default="cash", max_length=40)),
                ("reference", models.CharField(blank=True, default="", max_length=120)),
                ("status", models.CharField(default="success", max_length=40)),
                ("paid_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(db_index=True)),
                ("updated_at", models.DateTimeField(db_index=True)),
                ("is_synced", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Mobile Payment",
                "verbose_name_plural": "Mobile Payments",
                "ordering": ["-paid_at"],
            },
        ),
    ]

