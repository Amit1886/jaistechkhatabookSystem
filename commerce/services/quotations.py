from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from commerce.models import Order, OrderItem, Quotation, QuotationAuditLog, QuotationItem


def _dec(value, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal(default)


def add_audit_log(
    *,
    quotation: Quotation,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    performed_by=None,
    note: str = "",
) -> None:
    QuotationAuditLog.objects.create(
        quotation=quotation,
        action=(action or "").strip()[:40] or "action",
        from_status=(from_status or "").strip()[:16],
        to_status=(to_status or "").strip()[:16],
        performed_by=performed_by,
        note=(note or "").strip()[:255],
    )


def assert_status_transition(quotation: Quotation, to_status: str) -> None:
    cur = (quotation.status or "").strip().lower()
    nxt = (to_status or "").strip().lower()

    if cur == Quotation.Status.CONVERTED:
        raise ValueError("Converted quotation cannot be changed.")

    if cur == Quotation.Status.REJECTED and nxt != Quotation.Status.REJECTED:
        raise ValueError("Rejected quotation cannot be changed.")

    if nxt == Quotation.Status.APPROVED and cur != Quotation.Status.VERIFIED:
        raise ValueError("Only Verified quotations can be Approved.")

    if nxt == Quotation.Status.CONVERTED and cur != Quotation.Status.APPROVED:
        raise ValueError("Only Approved quotations can be Converted.")


@transaction.atomic
def transition_status(
    *,
    quotation_id: int,
    to_status: str,
    performed_by=None,
    action: str,
    note: str = "",
) -> Quotation:
    quotation = Quotation.objects.select_for_update().select_related("party", "warehouse", "converted_order").get(
        id=quotation_id
    )
    from_status = quotation.status
    assert_status_transition(quotation, to_status)

    quotation.status = to_status
    quotation.save(update_fields=["status"])
    add_audit_log(
        quotation=quotation,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=performed_by,
        note=note,
    )
    return quotation


def assert_convertible(quotation: Quotation) -> None:
    if (quotation.status or "").lower() != Quotation.Status.APPROVED:
        raise ValueError("Only Approved quotations can be converted.")
    if quotation.is_expired:
        raise ValueError("Cannot convert an expired quotation.")
    if (quotation.status or "").lower() == Quotation.Status.REJECTED:
        raise ValueError("Rejected quotation cannot be converted.")
    if quotation.converted_order_id:
        raise ValueError("Quotation is already converted.")


@dataclass(frozen=True)
class QuotationLine:
    product_id: int
    qty: Decimal
    rate: Decimal
    tax_percent: Decimal
    discount_amount: Decimal
    warehouse_id: int | None


def build_lines_from_items(items: Iterable[QuotationItem]) -> list[QuotationLine]:
    lines: list[QuotationLine] = []
    for it in items:
        try:
            product_id = int(it.product_id)
        except Exception:
            continue
        qty = _dec(it.qty)
        rate = _dec(it.rate)
        tax = _dec(it.tax)
        discount = _dec(it.discount)
        if qty <= Decimal("0.00"):
            continue
        lines.append(
            QuotationLine(
                product_id=product_id,
                qty=qty,
                rate=rate,
                tax_percent=tax,
                discount_amount=discount,
                warehouse_id=(int(it.warehouse_id) if it.warehouse_id else None),
            )
        )
    return lines


@transaction.atomic
def convert_quotation_to_order_now(*, quotation_id: int, performed_by=None) -> Order:
    """
    Admin-side conversion (no UI edit): immediately creates an Order + OrderItems and
    marks the quotation as Converted.
    """
    quotation = (
        Quotation.objects.select_for_update()
        .select_related("party", "warehouse", "converted_order")
        .prefetch_related("items")
        .get(id=quotation_id)
    )
    assert_convertible(quotation)

    owner = getattr(quotation.party, "owner", None) or quotation.created_by
    if not owner:
        raise ValueError("Quotation has no owner.")

    order = Order.objects.create(
        owner=owner,
        party=quotation.party,
        warehouse=quotation.warehouse,
        order_type="SALE",
        status="pending",
        order_source="Quotation",
        notes=f"From Quotation: {quotation.quotation_number}".strip(),
        quotation=quotation,
        tax_percent=_dec(quotation.items.first().tax if quotation.items.exists() else "0.00"),
    )

    lines = build_lines_from_items(quotation.items.all())
    if not lines:
        raise ValueError("Quotation has no items.")

    for line in lines:
        # OrderItem.qty is integer in this project; enforce whole-number qty.
        qty_int = int(line.qty)
        if qty_int <= 0:
            continue
        OrderItem.objects.create(
            order=order,
            product_id=line.product_id,
            qty=qty_int,
            price=_dec(line.rate),
            tax_percent=_dec(line.tax_percent),
            warehouse_id=line.warehouse_id or quotation.warehouse_id,
        )

    order.save()

    from_status = quotation.status
    quotation.status = Quotation.Status.CONVERTED
    quotation.converted_order = order
    quotation.save(update_fields=["status", "converted_order"])
    add_audit_log(
        quotation=quotation,
        action="convert",
        from_status=from_status,
        to_status=Quotation.Status.CONVERTED,
        performed_by=performed_by,
        note=f"Order #{order.id} created",
    )
    return order

