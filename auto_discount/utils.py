from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from .models import AppSettings, Customer, Product


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _q2(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_slabs(slabs: Iterable[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in slabs or []:
        try:
            min_qty = int(item.get("min_qty"))
            discount = _to_decimal(item.get("discount"))
        except Exception:
            continue
        if min_qty <= 0:
            continue
        if discount < 0:
            discount = Decimal("0")
        if discount > 100:
            discount = Decimal("100")
        normalized.append({"min_qty": min_qty, "discount": discount})
    normalized.sort(key=lambda x: x["min_qty"])
    return normalized


def _pick_discount(slabs: list[dict], qty: int) -> Decimal:
    """
    Pick the HIGHEST matching slab based on quantity.
    """
    picked = Decimal("0")
    for s in slabs:
        if qty >= int(s["min_qty"]):
            picked = _to_decimal(s["discount"])
    return picked


@dataclass(frozen=True)
class DiscountResult:
    final_price: Decimal
    applied_discount: Decimal
    is_adjusted: bool
    minimum_profit_price: Decimal


def calculate_auto_discount(product: Product, qty: int, customer_type: str) -> DiscountResult:
    """
    Calculates auto discount for a single product unit price.

    RULES:
    - Picks highest matching slab (by min_qty)
    - Applies discount on product.selling_price
    - Enforces NO-LOSS floor:
        final_price >= purchase_price + (purchase_price * min_profit_percentage / 100)
    - If discount breaks the rule, auto-reduces discount so final price stays at/above floor.
    - If product.selling_price itself is below floor, final price is raised to the floor.
    """
    qty = int(qty or 0)
    if qty < 0:
        qty = 0

    settings = AppSettings.get_solo()

    purchase_price = _to_decimal(getattr(product, "purchase_price", 0))
    selling_price = _to_decimal(getattr(product, "selling_price", 0))
    min_profit_pct = _to_decimal(getattr(settings, "min_profit_percentage", 10))
    if min_profit_pct < 0:
        min_profit_pct = Decimal("0")

    minimum_profit_price = purchase_price + (purchase_price * min_profit_pct / Decimal("100"))
    minimum_profit_price = _q2(minimum_profit_price)

    if not getattr(settings, "enable_auto_discount", True):
        # Still enforce no-loss floor
        final_price = selling_price
        applied_discount = Decimal("0")
        is_adjusted = False
        if final_price < minimum_profit_price:
            final_price = minimum_profit_price
            is_adjusted = True
        return DiscountResult(_q2(final_price), _q2(applied_discount), bool(is_adjusted), minimum_profit_price)

    slabs_raw = settings.b2b_slabs if str(customer_type).lower() == Customer.CustomerType.B2B else settings.b2c_slabs
    slabs = _normalize_slabs(slabs_raw or [])
    requested_discount = _pick_discount(slabs, qty)
    requested_discount = _q2(requested_discount)

    if selling_price <= 0:
        # Nothing to discount; still enforce floor.
        final_price = minimum_profit_price if minimum_profit_price > 0 else Decimal("0")
        return DiscountResult(_q2(final_price), Decimal("0.00"), True, minimum_profit_price)

    discounted_price = selling_price * (Decimal("100") - requested_discount) / Decimal("100")
    discounted_price = _q2(discounted_price)

    if discounted_price >= minimum_profit_price:
        return DiscountResult(discounted_price, requested_discount, False, minimum_profit_price)

    # Discount violates no-loss rule -> reduce discount to maximum allowed.
    # allowed_discount = (1 - minimum_profit_price/selling_price) * 100
    try:
        allowed_discount = (Decimal("1") - (minimum_profit_price / selling_price)) * Decimal("100")
    except Exception:
        allowed_discount = Decimal("0")
    if allowed_discount < 0:
        allowed_discount = Decimal("0")
    if allowed_discount > requested_discount:
        # If selling_price already >= floor, allowed_discount should never exceed requested_discount here,
        # but keep it safe.
        allowed_discount = requested_discount

    allowed_discount = _q2(allowed_discount)
    final_price = selling_price * (Decimal("100") - allowed_discount) / Decimal("100")
    final_price = _q2(final_price)

    # Final absolute safety clamp
    if final_price < minimum_profit_price:
        final_price = minimum_profit_price

    return DiscountResult(final_price, allowed_discount, True, minimum_profit_price)

