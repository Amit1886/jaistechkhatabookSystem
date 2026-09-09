from django.db import models
from django.conf import settings


class GSTRegistration(models.Model):
    business = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gst_registrations",
    )
    gstin = models.CharField(max_length=15, unique=True)
    legal_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    registration_type = models.CharField(max_length=50)
    status = models.CharField(max_length=50, default="active")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.gstin


class GSTCategory(models.Model):
    CATEGORY_CHOICES = [
        ("goods", "Goods"),
        ("services", "Services"),
        ("composite", "Composite"),
    ]

    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    hsn_code = models.CharField(max_length=20, blank=True)
    sac_code = models.CharField(max_length=20, blank=True)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "GST Categories"
        unique_together = ("name", "category_type")

    def __str__(self):
        return f"{self.name} ({self.category_type})"


class GSTTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("sale", "Sale"),
        ("purchase", "Purchase"),
        ("export", "Export"),
        ("import", "Import"),
    ]

    registration = models.ForeignKey(
        GSTRegistration,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    invoice_number = models.CharField(max_length=60)
    invoice_date = models.DateField()
    counterparty_name = models.CharField(max_length=255)
    counterparty_gstin = models.CharField(max_length=15, blank=True)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.registration.gstin}"


class FiscalYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class FiscalPeriod(models.Model):
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.CASCADE,
        related_name="periods",
    )
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        unique_together = ("fiscal_year", "name")

    def __str__(self):
        return f"{self.fiscal_year.name} - {self.name}"


class GSTR1(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("filed", "Filed"),
        ("cancelled", "Cancelled"),
    ]

    registration = models.ForeignKey(
        GSTRegistration,
        on_delete=models.CASCADE,
        related_name="gstr1_returns",
    )
    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    filed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GSTR-1 - {self.registration.gstin}"


class GSTR3B(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("filed", "Filed"),
        ("cancelled", "Cancelled"),
    ]

    registration = models.ForeignKey(
        GSTRegistration,
        on_delete=models.CASCADE,
        related_name="gstr3b_returns",
    )
    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cess = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    filed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GSTR-3B - {self.registration.gstin}"
