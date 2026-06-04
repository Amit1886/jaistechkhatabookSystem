from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


# ================================
# DUPLICATE INVOICE SETTINGS
# ================================
class DuplicateInvoiceSettings(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duplicate_invoice_settings",
        db_index=True,
    )

    enabled = models.BooleanField(default=True)
    window_minutes = models.PositiveIntegerField(default=60)
    strict_mode = models.BooleanField(default=False)
    similarity_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("90.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner"], name="uniq_dup_invoice_settings_owner"),
        ]

    def __str__(self):
        return f"Duplicate Invoice Settings ({self.owner})"

    @classmethod
    def get_for_owner(cls, owner):
        obj, _ = cls.objects.get_or_create(owner=owner)
        return obj


# ================================
# DUPLICATE INVOICE LOG
# ================================
class DuplicateInvoiceLog(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dup_logs_owner"   # ✅ FIX
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dup_logs_created"   # ✅ FIX
    )

    invoice = models.ForeignKey("commerce.Invoice", on_delete=models.CASCADE, related_name="duplicate_logs")
    possible_duplicate = models.ForeignKey(
        "commerce.Invoice",
        on_delete=models.CASCADE,
        related_name="possible_duplicate_logs"
    )

    similarity_score = models.DecimalField(max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
# ================================
# BUSINESS METRICS
# ================================
class BusinessMetric(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()

    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_expense = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    outstanding_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    stock_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    health_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "date"], name="uniq_business_metrics_owner_date"),
        ]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.owner_id} - {self.date} ({self.health_score})"


# ================================
# FESTIVAL CAMPAIGN
# ================================
class FestivalCampaign(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    theme = models.CharField(max_length=50, default="default")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    banner_image = models.ImageField(upload_to="festival_banners/", blank=True, null=True)

    products = models.ManyToManyField("commerce.Product", through="FestivalCampaignProduct", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def is_active_on(self, dt=None):
        day = dt or timezone.localdate()
        return self.status == "active" and self.start_date <= day <= self.end_date

    def discount_amount_for(self, amount):
        amount = Decimal(str(amount or 0))
        if self.discount_type == "percentage":
            return (amount * self.discount_value / 100).quantize(Decimal("0.01"))
        return self.discount_value


class FestivalCampaignProduct(models.Model):
    campaign = models.ForeignKey(FestivalCampaign, on_delete=models.CASCADE)
    product = models.ForeignKey("commerce.Product", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["campaign", "product"], name="uniq_festival_campaign_product"),
        ]


# ================================
# 🚀 FRAUD ALERT (FIX ADDED)
# ================================
class FraudAlert(models.Model):
    class AlertType(models.TextChoices):
        HIGH_AMOUNT = "high_amount", "High Amount"
        DUPLICATE = "duplicate", "Duplicate Transaction"
        SUDDEN_ACTIVITY = "sudden_activity", "Sudden Activity"
        CREDIT_RISK = "credit_risk", "Credit Risk"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    party = models.ForeignKey("khataapp.Party", on_delete=models.CASCADE)

    alert_type = models.CharField(max_length=50, choices=AlertType.choices)
    risk_score = models.FloatField(default=0)

    message = models.TextField()
    transaction = models.ForeignKey("khataapp.Transaction", on_delete=models.SET_NULL, null=True, blank=True)

    is_resolved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.party} - {self.alert_type} ({self.risk_score})"