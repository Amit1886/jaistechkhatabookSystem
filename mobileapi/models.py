from django.db import models


class MobileCustomer(models.Model):
    """
    Server-side mirror of the mobile (Flutter) offline-first `customers` table.

    Purpose: make mobile-created data visible in Django Admin after sync,
    without forcing an immediate mapping into the full desktop schema.

    Primary key is the mobile-generated string ID.
    """

    id = models.CharField(max_length=80, primary_key=True)
    user_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40, blank=True, default="")
    address = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    is_synced = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Mobile Customer"
        verbose_name_plural = "Mobile Customers"

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"


class MobileProduct(models.Model):
    """Server-side mirror of the mobile `products` table."""

    id = models.CharField(max_length=80, primary_key=True)
    user_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=80, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    is_synced = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Mobile Product"
        verbose_name_plural = "Mobile Products"

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"


class MobileInvoice(models.Model):
    """Server-side mirror of the mobile `invoices` table."""

    id = models.CharField(max_length=80, primary_key=True)
    user_id = models.CharField(max_length=80, db_index=True)
    customer_id = models.CharField(max_length=80, db_index=True)
    number = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=20, db_index=True, default="unpaid")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    is_synced = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mobile Invoice"
        verbose_name_plural = "Mobile Invoices"

    def __str__(self) -> str:
        return f"{self.number} ({self.user_id})"


class MobileInvoiceItem(models.Model):
    """Server-side mirror of the mobile `invoice_items` table."""

    id = models.CharField(max_length=80, primary_key=True)
    invoice_id = models.CharField(max_length=80, db_index=True)
    product_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    is_synced = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mobile Invoice Item"
        verbose_name_plural = "Mobile Invoice Items"

    def __str__(self) -> str:
        return f"{self.invoice_id} - {self.name}"


class MobilePayment(models.Model):
    """Server-side mirror of the mobile `payments` table."""

    id = models.CharField(max_length=80, primary_key=True)
    invoice_id = models.CharField(max_length=80, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mode = models.CharField(max_length=40, default="cash")
    reference = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=40, default="success")
    paid_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    is_synced = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-paid_at"]
        verbose_name = "Mobile Payment"
        verbose_name_plural = "Mobile Payments"

    def __str__(self) -> str:
        return f"{self.invoice_id} {self.amount} ({self.mode})"
