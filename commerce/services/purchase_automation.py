from __future__ import annotations

import logging
import random
import string
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Optional

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from datetime import timedelta

from ai_ocr.data_parser import ParsedInvoice
from commerce.models import Inventory, Order, OrderItem, Product
from khataapp.models import Party

logger = logging.getLogger(__name__)


def _to_decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v).replace(",", "").strip())
    except Exception:
        return Decimal("0.00")


def _mk_sku(prefix: str = "SKU") -> str:
    rand = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}-{timezone.localdate().strftime('%y%m%d')}-{rand}"


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=a.lower().strip(), b=b.lower().strip()).ratio()


def match_product(owner, *, name: str) -> Optional[Product]:
    """
    Best-effort fuzzy product match for OCR extracted item names.
    """
    q = (name or "").strip()
    if not q:
        return None

    # 1) Direct contains search (fast)
    words = [w for w in q.replace("/", " ").replace("-", " ").split() if len(w) >= 3][:5]
    qs = Product.objects.filter(owner=owner)
    if words:
        cond = Q()
        for w in words:
            cond |= Q(name__icontains=w)
        qs = qs.filter(cond)
    cand = list(qs.order_by("name")[:80])

    # 2) If nothing found, widen a bit but still capped
    if not cand:
        cand = list(Product.objects.filter(owner=owner).order_by("name")[:80])

    best = None
    best_score = 0.0
    for p in cand:
        score = _similarity(q, p.name or "")
        if score > best_score:
            best_score = score
            best = p

    if best and best_score >= 0.76:
        return best
    return None


@dataclass(frozen=True)
class PurchaseCreateResult:
    ok: bool
    order: Optional[Order] = None
    created_products: int = 0
    updated_stock_items: int = 0
    total_amount: Decimal = Decimal("0.00")
    error: str = ""


@transaction.atomic
def create_purchase_from_invoice(
    *,
    owner,
    supplier: Party,
    parsed: ParsedInvoice,
    auto_update_stock: bool = True,
) -> PurchaseCreateResult:
    if not supplier or supplier.party_type != "supplier":
        return PurchaseCreateResult(ok=False, error="not_a_supplier")

    items = parsed.items if parsed and isinstance(parsed.items, list) else []
    if not items:
        return PurchaseCreateResult(ok=False, error="no_items_detected")

    total = _to_decimal((parsed.totals or {}).get("total") or "0")
    if total <= 0:
        # fallback sum
        for it in items:
            total += _to_decimal(it.get("amount") or "0")

    due_date = None
    try:
        due_days = int(getattr(supplier, "credit_period", 30) or 30)
        due_date = timezone.localdate() + timedelta(days=max(0, min(due_days, 365)))
    except Exception:
        due_date = None

    order = Order.objects.create(
        owner=owner,
        party=supplier,
        status="accepted",
        order_type="PURCHASE",
        placed_by="party",
        order_source="WhatsApp OCR",
        invoice_number=(parsed.invoice_no or "")[:50] or None,
        due_amount=total,
        payment_due_date=due_date,
        notes=(parsed.supplier_name or "")[:200] if parsed else "",
    )

    created_products = 0
    updated_stock_items = 0

    for it in items[:200]:
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        qty = int(_to_decimal(it.get("qty") or "1") or 1)
        if qty <= 0:
            continue
        rate = _to_decimal(it.get("rate") or "0")
        amount = _to_decimal(it.get("amount") or "0")
        if rate <= 0 and qty > 0 and amount > 0:
            try:
                rate = (amount / Decimal(str(qty))).quantize(Decimal("0.01"))
            except Exception:
                rate = Decimal("0.00")

        product = match_product(owner, name=name)
        raw_name = ""
        if not product:
            sku = _mk_sku("NEW")
            product = Product.objects.create(
                owner=owner,
                name=name[:100],
                sku=sku,
                price=rate if rate > 0 else Decimal("0.00"),
                stock=0,
                min_stock=0,
                unit="pcs",
                description="Created by WhatsApp OCR",
            )
            created_products += 1
        else:
            raw_name = ""  # matched

        OrderItem.objects.create(
            order=order,
            product=product,
            qty=int(qty),
            price=rate if rate > 0 else _to_decimal(getattr(product, "price", 0)),
            raw_name=raw_name,
        )

        if auto_update_stock:
            try:
                Product.objects.filter(id=product.id).update(stock=F("stock") + int(qty))
            except Exception:
                pass
            try:
                inv, created = Inventory.objects.get_or_create(owner=owner, product=product, defaults={"stock": int(qty)})
                if not created:
                    inv.stock = int(inv.stock or 0) + int(qty)
                    inv.save(update_fields=["stock", "updated_at"])
            except Exception:
                pass
            updated_stock_items += 1

    return PurchaseCreateResult(
        ok=True,
        order=order,
        created_products=created_products,
        updated_stock_items=updated_stock_items,
        total_amount=total,
    )
