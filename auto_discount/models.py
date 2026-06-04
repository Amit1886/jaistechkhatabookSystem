from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from solo.models import SingletonModel


def _validate_slabs(value: Any) -> None:
    """
    Slabs must be a list of objects:
    [
      {"min_qty": 5, "discount": 2},
      {"min_qty": 20, "discount": 5},
      ...
    ]
    """
    if value in (None, ""):
        return
    if not isinstance(value, list):
        raise ValidationError("Slabs must be a JSON list.")

    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"Slab #{i+1} must be a JSON object.")
        if "min_qty" not in item or "discount" not in item:
            raise ValidationError(f"Slab #{i+1} must contain 'min_qty' and 'discount'.")

        try:
            min_qty = int(item.get("min_qty"))
        except Exception:
            raise ValidationError(f"Slab #{i+1} min_qty must be an integer.")
        if min_qty <= 0:
            raise ValidationError(f"Slab #{i+1} min_qty must be > 0.")

        try:
            discount = Decimal(str(item.get("discount")))
        except Exception:
            raise ValidationError(f"Slab #{i+1} discount must be a number.")
        if discount < 0 or discount > 100:
            raise ValidationError(f"Slab #{i+1} discount must be between 0 and 100.")


class AppSettings(SingletonModel):
    """
    Global settings for the auto-discount engine.

    IMPORTANT:
    - `min_profit_percentage` enforces a no-loss floor price.
    - Slabs are quantity-based discounts in percentage.
    """

    min_profit_percentage = models.FloatField(default=10)
    enable_auto_discount = models.BooleanField(default=True)

    b2b_slabs = models.JSONField(default=list, blank=True, validators=[_validate_slabs])
    b2c_slabs = models.JSONField(default=list, blank=True, validators=[_validate_slabs])

    def clean(self):
        super().clean()
        if self.min_profit_percentage < 0:
            raise ValidationError({"min_profit_percentage": "Must be >= 0."})
        # Ensure validators run with user-friendly errors
        _validate_slabs(self.b2b_slabs)
        _validate_slabs(self.b2c_slabs)

    def __str__(self) -> str:
        return "Auto Discount Settings"


class Product(models.Model):
    """
    Minimal Product model required by the engine.
    If your project already has a Product model, you can adapt the utils to use it.
    """

    name = models.CharField(max_length=200)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    stock = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class Customer(models.Model):
    class CustomerType(models.TextChoices):
        B2B = "b2b", "B2B"
        B2C = "b2c", "B2C"

    name = models.CharField(max_length=200)
    customer_type = models.CharField(max_length=10, choices=CustomerType.choices, default=CustomerType.B2C, db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.customer_type.upper()})"

