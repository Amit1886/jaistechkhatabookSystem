from decimal import Decimal

from django.db import models


class CommissionRule(models.Model):
    name = models.CharField(max_length=100, unique=True)
    salesman_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    delivery_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CommissionPayout(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="commission_payouts")
    rule = models.ForeignKey(CommissionRule, on_delete=models.SET_NULL, null=True)
    margin_amount = models.DecimalField(max_digits=14, decimal_places=2)
    salesman_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    delivery_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    company_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["order", "created_at"])]


class CommissionScheme(models.Model):
    EVENT_CHOICES = [
        ("signup", "Signup"),
        ("subscription", "Subscription"),
        ("renewal", "Renewal"),
        ("bonus", "Bonus"),
        ("order", "Order"),
        ("call_conversion", "Call Conversion"),
        ("qr_scan", "QR Scan"),
        ("shop_onboarding", "Shop Onboarding"),
        ("voice_close", "Voice AI Close"),
    ]
    ROLE_CHOICES = [
        ("super_admin", "SuperAdmin"),
        ("state_admin", "StateAdmin"),
        ("district_admin", "DistrictAdmin"),
        ("area_admin", "AreaAdmin"),
        ("super_agent", "SuperAgent"),
        ("agent", "Agent"),
        ("customer", "Customer"),
    ]
    name = models.CharField(max_length=120)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)
    percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event_type", "role")
        ordering = ["event_type", "role"]

    def __str__(self):
        return f"{self.event_type}:{self.role}:{self.percent}"
