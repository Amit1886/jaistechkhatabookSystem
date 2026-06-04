from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from storefront.models import StoreOrder
from vendors.models import Vendor, VendorCustomerCompanyMember, VendorCustomerSegment


def _safe_int(v, default=None):
    try:
        if v is None:
            return default
        return int(str(v).strip())
    except Exception:
        return default


def _safe_decimal(v, default=Decimal("0")):
    try:
        if v is None:
            return default
        return Decimal(str(v).strip() or "0")
    except Exception:
        return default


def customer_queryset_for_vendor(vendor: Vendor):
    """
    Customers that have at least one (non-cancelled) order in this vendor store.
    """

    User = get_user_model()
    ok_statuses = [
        StoreOrder.Status.PENDING,
        StoreOrder.Status.ACCEPTED,
        StoreOrder.Status.PACKED,
        StoreOrder.Status.SHIPPED,
        StoreOrder.Status.DELIVERED,
    ]
    return User.objects.filter(store_orders__vendor=vendor, store_orders__status__in=ok_statuses).distinct()


def apply_segment_rules(qs, *, vendor: Vendor, rules: dict):
    """
    Applies Phase A rules on a customer queryset.
    """

    rules = rules or {}
    pincode = (rules.get("pincode") or "").strip()
    if pincode:
        qs = qs.filter(store_orders__vendor=vendor, store_orders__address__pincode__iexact=pincode)

    min_orders = _safe_int(rules.get("min_orders"))
    min_spent = _safe_decimal(rules.get("min_spent"), default=None)

    if min_orders is not None or min_spent is not None:
        ok_statuses = [
            StoreOrder.Status.ACCEPTED,
            StoreOrder.Status.PACKED,
            StoreOrder.Status.SHIPPED,
            StoreOrder.Status.DELIVERED,
        ]
        qs = qs.annotate(
            _seg_orders=Count(
                "store_orders",
                filter=Q(store_orders__vendor=vendor, store_orders__status__in=ok_statuses),
                distinct=True,
            ),
            _seg_spent=Sum(
                "store_orders__total_amount",
                filter=Q(store_orders__vendor=vendor, store_orders__status__in=ok_statuses),
            ),
        )
        if min_orders is not None:
            qs = qs.filter(_seg_orders__gte=min_orders)
        if min_spent is not None:
            qs = qs.filter(_seg_spent__gte=min_spent)

    has_company = rules.get("has_company")
    if has_company in {True, "true", "1", 1, "yes"}:
        qs = qs.filter(vendor_company_memberships__company__vendor=vendor, vendor_company_memberships__is_active=True)
    elif has_company in {False, "false", "0", 0, "no"}:
        qs = qs.exclude(vendor_company_memberships__company__vendor=vendor, vendor_company_memberships__is_active=True)

    return qs.distinct()


def preview_segment(*, segment: VendorCustomerSegment, limit: int = 50):
    qs = customer_queryset_for_vendor(segment.vendor)
    qs = apply_segment_rules(qs, vendor=segment.vendor, rules=(segment.rules_json or {}))
    return qs.order_by("-last_login", "-id")[: max(1, min(int(limit or 50), 200))]


def segment_count(*, segment: VendorCustomerSegment) -> int:
    qs = customer_queryset_for_vendor(segment.vendor)
    qs = apply_segment_rules(qs, vendor=segment.vendor, rules=(segment.rules_json or {}))
    return qs.count()

