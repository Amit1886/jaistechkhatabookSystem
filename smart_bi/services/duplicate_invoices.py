from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Prefetch
from django.utils import timezone

from commerce.models import Invoice, Order, OrderItem
from smart_bi.models import DuplicateInvoiceLog, DuplicateInvoiceSettings


@dataclass(frozen=True)
class DuplicateInvoiceCandidate:
    invoice: Invoice
    similarity_score: Decimal
    product_summary: str


def _order_line_key(item: OrderItem) -> str:
    qty = getattr(item, "qty", None)
    try:
        qty_int = int(Decimal(str(qty or 0)))
    except Exception:
        qty_int = 0
    if getattr(item, "product_id", None):
        return f"p{int(item.product_id)}:{qty_int}"
    raw = (getattr(item, "raw_name", "") or "").strip().lower()
    return f"n{raw}:{qty_int}"


def _build_order_signature(order: Order) -> set[str]:
    keys: list[str] = []
    for it in order.items.all():
        keys.append(_order_line_key(it))
    return set(keys)


def _format_product_summary(order: Order, *, max_items: int = 6) -> str:
    parts: list[str] = []
    for it in order.items.all().select_related("product").order_by("id"):
        name = ""
        if getattr(it, "product", None):
            name = (it.product.name or "").strip()
        if not name:
            name = (getattr(it, "raw_name", "") or "Unknown").strip()
        qty = getattr(it, "qty", 0) or 0
        parts.append(f"{name} x {qty}")
        if len(parts) >= max_items:
            break

    more = max(0, order.items.count() - len(parts))
    if more:
        parts.append(f"+{more} more")
    return ", ".join(parts) if parts else "-"


def _amount_matches(a: Decimal, b: Decimal, *, tol: Decimal = Decimal("0.01")) -> bool:
    try:
        a = Decimal(str(a or 0)).quantize(Decimal("0.01"))
        b = Decimal(str(b or 0)).quantize(Decimal("0.01"))
        return abs(a - b) <= tol
    except Exception:
        return False


def find_possible_duplicate_invoices(
    *,
    order: Order,
    settings: DuplicateInvoiceSettings | None = None,
    max_results: int = 5,
) -> list[DuplicateInvoiceCandidate]:
    """
    Find possible duplicate invoices for the given order.

    Criteria:
    - Same customer (Party)
    - Within configurable window
    - Invoice amount matches (tolerance 0.01)
    - Product+quantity similarity meets threshold (soft) or exact match (strict)
    """
    owner = getattr(order, "owner", None)
    if not owner:
        return []

    party_id = getattr(order, "party_id", None)
    if not party_id:
        return []

    settings = settings or DuplicateInvoiceSettings.get_for_owner(owner)
    if not getattr(settings, "enabled", True):
        return []

    try:
        window_minutes = int(getattr(settings, "window_minutes", 60) or 60)
    except Exception:
        window_minutes = 60
    if window_minutes <= 0:
        return []

    window_start = timezone.now() - timedelta(minutes=window_minutes)
    new_amount = order.total_amount()
    new_sig = _build_order_signature(order)
    if not new_sig:
        return []

    item_qs = OrderItem.objects.select_related("product").all()
    invoice_qs = (
        Invoice.objects.select_related("order", "order__party")
        .prefetch_related(Prefetch("order__items", queryset=item_qs))
        .filter(
            order__owner=owner,
            order__party_id=party_id,
            created_at__gte=window_start,
        )
        .exclude(order_id=order.id)
        .order_by("-created_at", "-id")
    )

    strict = bool(getattr(settings, "strict_mode", False))
    try:
        threshold = Decimal(str(getattr(settings, "similarity_threshold", Decimal("90.00"))))
    except Exception:
        threshold = Decimal("90.00")

    candidates: list[DuplicateInvoiceCandidate] = []
    for inv in invoice_qs[:50]:
        if not _amount_matches(new_amount, inv.amount):
            continue
        inv_sig = _build_order_signature(inv.order)
        union = new_sig | inv_sig
        if not union:
            continue
        intersection = new_sig & inv_sig
        score = (Decimal(len(intersection)) / Decimal(len(union))) * Decimal("100.00")
        score = score.quantize(Decimal("0.01"))

        if strict:
            if score < Decimal("100.00"):
                continue
        else:
            if score < threshold:
                continue

        candidates.append(
            DuplicateInvoiceCandidate(
                invoice=inv,
                similarity_score=score,
                product_summary=_format_product_summary(inv.order),
            )
        )

    candidates.sort(key=lambda c: (c.similarity_score, c.invoice.created_at), reverse=True)
    return candidates[:max_results]


def log_possible_duplicates(
    *,
    owner,
    created_by,
    invoice: Invoice,
    candidates: Iterable[DuplicateInvoiceCandidate],
) -> int:
    """
    Persist duplicate candidates for an invoice (idempotent per invoice).
    """
    DuplicateInvoiceLog.objects.filter(owner=owner, invoice=invoice).delete()
    rows = []
    for c in candidates:
        rows.append(
            DuplicateInvoiceLog(
                owner=owner,
                created_by=created_by,
                invoice=invoice,
                possible_duplicate=c.invoice,
                similarity_score=c.similarity_score,
            )
        )
    if not rows:
        return 0
    created = DuplicateInvoiceLog.objects.bulk_create(rows, ignore_conflicts=False)
    return len(created)

