from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from commerce.models import Coupon, CouponUsage
from storefront.models import VendorCoupon


@dataclass(frozen=True)
class CouponQuote:
    coupon: Coupon
    discount_amount: Decimal


def available_coupons_for_vendor(*, vendor) -> list[Coupon]:
    """
    Coupons enabled for a vendor storefront.
    Only returns currently valid/active coupons.
    """
    now = timezone.now()
    base = Coupon.objects.filter(is_active=True, coupon_type="discount", valid_from__lte=now).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=now)
    )
    # If vendor hasn't configured coupons yet, show all active coupons (admin-driven defaults).
    if not VendorCoupon.objects.filter(vendor=vendor).exists():
        return list(base.order_by("-created_at")[:20])
    qs = base.filter(vendor_coupons__vendor=vendor, vendor_coupons__is_active=True).distinct()
    return list(qs.order_by("-created_at")[:20])


def quote_coupon(
    *,
    vendor,
    code: str,
    user=None,
    subtotal: Decimal,
) -> tuple[Optional[CouponQuote], str]:
    """
    Returns (quote, error_code). When quote is not None, error_code is "".
    """
    code = (code or "").strip().upper()
    if not code:
        return None, "missing_code"

    coupon = Coupon.objects.filter(code__iexact=code, is_active=True).order_by("-created_at").first()
    if not coupon or not coupon.is_valid() or coupon.coupon_type != "discount":
        return None, "invalid_coupon"

    # Vendor-scoped enablement: if vendor has any coupon config, enforce it.
    if VendorCoupon.objects.filter(vendor=vendor).exists():
        if not VendorCoupon.objects.filter(vendor=vendor, coupon=coupon, is_active=True).exists():
            return None, "not_enabled_for_store"

    if Decimal(str(subtotal or "0")) < Decimal(str(coupon.min_order_amount or "0")):
        return None, "min_order_not_met"

    # Usage limits (best-effort). For guests, per-user limit is re-checked at checkout after user is created.
    total_used = CouponUsage.objects.filter(coupon=coupon).count()
    if coupon.usage_limit and total_used >= int(coupon.usage_limit):
        return None, "usage_limit_reached"

    if user and getattr(user, "is_authenticated", False):
        user_used = CouponUsage.objects.filter(coupon=coupon, user=user).count()
        if coupon.per_user_limit and user_used >= int(coupon.per_user_limit):
            return None, "per_user_limit_reached"

    discount = coupon.get_discount_amount(Decimal(str(subtotal or "0"))).quantize(Decimal("0.01"))
    if discount <= 0:
        return None, "no_discount"

    return CouponQuote(coupon=coupon, discount_amount=discount), ""
