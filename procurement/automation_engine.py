from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from commerce.models import Invoice, Order, OrderItem, Product
from khataapp.models import Party
from procurement.models import (
    AITrainingLog,
    InvoiceSource,
    ProductUnit,
    SupplierProduct,
    PurchaseDraft,
    PurchaseDraftItem,
    PurchaseInvoice,
    PurchaseItem,
    SupplierProductAlias,
    SupplierTemplate,
)

logger = logging.getLogger(__name__)


DECIMAL_ZERO = Decimal("0.00")


def _to_decimal(value: Any, default: Decimal = DECIMAL_ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return default


def _parse_date(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    # Common invoice formats
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except Exception:
            continue
    return None


_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9\s]+")


def _norm_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("kgs", "kg").replace("kilogram", "kg").replace("kilograms", "kg")
    t = t.replace("gms", "g").replace("grams", "g").replace("gram", "g")
    t = t.replace("ltr", "l").replace("litre", "l").replace("liters", "l").replace("litres", "l")
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def _tokenize(text: str) -> list[str]:
    t = _norm_text(text)
    if not t:
        return []
    toks = [x for x in t.split(" ") if x]
    return toks[:40]


def _jaccard(a: Iterable[str], b: Iterable[str]) -> Decimal:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return Decimal("0.0")
    inter = len(sa & sb)
    union = len(sa | sb)
    if union <= 0:
        return Decimal("0.0")
    return Decimal(str(inter / union))


def _sequence_ratio(a: str, b: str) -> Decimal:
    # Lightweight fallback; avoids extra dependencies.
    try:
        import difflib

        return Decimal(str(difflib.SequenceMatcher(None, a, b).ratio()))
    except Exception:
        return Decimal("0.0")


def _similarity(a: str, b: str) -> Decimal:
    a_n = _norm_text(a)
    b_n = _norm_text(b)
    if not a_n or not b_n:
        return Decimal("0.0")
    tok = _jaccard(_tokenize(a_n), _tokenize(b_n))
    seq = _sequence_ratio(a_n, b_n)
    # Weighted blend: token overlap is more robust for word-order changes.
    score = (tok * Decimal("0.65")) + (seq * Decimal("0.35"))
    if score < 0:
        return Decimal("0.0")
    if score > 1:
        return Decimal("1.0")
    return score


def get_or_create_supplier(owner, supplier_name: str) -> Party:
    name = (supplier_name or "").strip() or "Unknown Supplier"
    party = Party.objects.filter(owner=owner, party_type="supplier", name__iexact=name).first()
    if party:
        return party
    # Best-effort: avoid creating noise for very short/garbled names.
    if len(name) < 3:
        name = "OCR Supplier"
    return Party.objects.create(owner=owner, party_type="supplier", name=name[:100])


@dataclass(frozen=True)
class ProductMatch:
    product: Optional[Product]
    confidence: Decimal
    method: str


def _match_from_alias(owner, supplier: Party, raw_name: str) -> Optional[ProductMatch]:
    nm = _norm_text(raw_name)
    if not nm or not supplier:
        return None
    alias = (
        SupplierProductAlias.objects.filter(owner=owner, supplier=supplier, normalized_name=nm)
        .select_related("product")
        .first()
    )
    if not alias:
        return None
    # Update usage counters best-effort (do not fail matching).
    try:
        SupplierProductAlias.objects.filter(id=alias.id).update(
            times_used=F("times_used") + 1,
            last_used_at=timezone.now(),
            updated_at=timezone.now(),
        )
    except Exception:
        pass
    return ProductMatch(product=alias.product, confidence=alias.confidence, method="alias")


def _best_product_match(owner, supplier: Optional[Party], raw_name: str, *, threshold: Decimal = Decimal("0.82")) -> ProductMatch:
    raw = (raw_name or "").strip()
    if not raw:
        return ProductMatch(product=None, confidence=Decimal("0.0"), method="")

    if supplier is not None:
        alias_match = _match_from_alias(owner, supplier, raw)
        if alias_match:
            return alias_match

    # Exact match by product name (fast path)
    exact = Product.objects.filter(owner=owner, name__iexact=raw).first()
    if exact:
        return ProductMatch(product=exact, confidence=Decimal("1.0"), method="exact")

    # Fuzzy match across owner's products.
    # Keep it bounded for safety; fall back to contains if the catalog is huge.
    qs = Product.objects.filter(owner=owner).only("id", "name", "sku")[:3000]
    best_prod: Optional[Product] = None
    best_score = Decimal("0.0")
    for p in qs:
        score = _similarity(raw, p.name or "")
        if score > best_score:
            best_score = score
            best_prod = p
    if best_prod and best_score >= threshold:
        return ProductMatch(product=best_prod, confidence=best_score.quantize(Decimal("0.001")), method="fuzzy")

    # Contains fallback (better recall, lower confidence).
    contains = Product.objects.filter(owner=owner, name__icontains=raw[:20]).order_by("name").first()
    if contains:
        return ProductMatch(product=contains, confidence=Decimal("0.650"), method="contains")

    return ProductMatch(product=None, confidence=best_score.quantize(Decimal("0.001")), method="unmatched")


def _unit_alias(template: Optional[SupplierTemplate]) -> dict[str, str]:
    if not template:
        return {}
    tpl = template.template or {}
    if not isinstance(tpl, dict):
        return {}
    ua = tpl.get("unit_aliases") or {}
    if isinstance(ua, dict):
        return {str(k).strip().lower(): str(v).strip().lower() for k, v in ua.items() if str(k).strip() and str(v).strip()}
    return {}


def apply_supplier_template_to_draft(draft: PurchaseDraft) -> None:
    if not draft or not draft.supplier_id:
        return
    template = SupplierTemplate.objects.filter(owner=draft.owner, supplier_id=draft.supplier_id, is_active=True).order_by("-updated_at", "-id").first()
    if not template:
        return

    unit_aliases = _unit_alias(template)
    for it in draft.items.all():
        raw_name = (it.raw_name or "").strip()
        it.raw_name = raw_name[:200]
        u = (it.unit or "").strip().lower()
        if u and unit_aliases:
            it.unit = unit_aliases.get(u, u)[:30]
        it.save(update_fields=["raw_name", "unit"])

    SupplierTemplate.objects.filter(id=template.id).update(last_used_at=timezone.now())


def normalize_units_for_draft(draft: PurchaseDraft) -> None:
    if not draft:
        return
    for it in draft.items.select_related("matched_product").all():
        unit = (it.unit or "").strip().lower()
        qty = _to_decimal(it.quantity, DECIMAL_ZERO)
        prod = it.matched_product
        if not prod:
            it.normalized_quantity = qty
            it.normalized_unit = unit or ""
            it.save(update_fields=["normalized_quantity", "normalized_unit"])
            continue

        base_unit = (getattr(prod, "unit", "") or "").strip().lower()
        if not base_unit:
            base_unit = unit or ""

        if not unit or unit == base_unit:
            it.normalized_quantity = qty
            it.normalized_unit = base_unit
            it.save(update_fields=["normalized_quantity", "normalized_unit"])
            continue

        rules = list(
            ProductUnit.objects.filter(owner=draft.owner, product=prod, is_active=True)
            .only("id", "unit_name", "multiplier", "synonyms", "updated_at")
            .order_by("-updated_at", "-id")[:50]
        )
        rule = next((r for r in rules if (r.unit_name or "").strip().lower() == unit), None)
        if not rule:
            for r in rules:
                syn = r.synonyms or []
                if not isinstance(syn, list):
                    continue
                syn_norm = {str(x).strip().lower() for x in syn if str(x).strip()}
                if unit in syn_norm:
                    rule = r
                    break

        if not rule:
            it.normalized_quantity = qty
            it.normalized_unit = unit
            it.requires_review = True
            it.notes = (it.notes or "")[:200]
            it.save(update_fields=["normalized_quantity", "normalized_unit", "requires_review", "notes"])
            continue

        mult = _to_decimal(rule.multiplier, Decimal("1.0"))
        it.normalized_quantity = (qty * mult).quantize(Decimal("0.000001"))
        it.normalized_unit = base_unit
        it.save(update_fields=["normalized_quantity", "normalized_unit"])


def detect_duplicate_purchase_invoice(*, owner, supplier: Optional[Party], invoice_number: str, invoice_date: Optional[date], total_amount: Decimal) -> Optional[Order]:
    inv_no = (invoice_number or "").strip()
    if not owner or not supplier or not inv_no:
        return None

    qs = Order.objects.filter(owner=owner, party=supplier, order_type="PURCHASE")
    dup = qs.filter(invoice_number__iexact=inv_no).order_by("-created_at", "-id").first()
    if dup:
        return dup

    # Fallback (best-effort): invoice amount/date proximity via Invoice table.
    if not invoice_date:
        return None
    dt_from = timezone.make_aware(datetime.combine(invoice_date, datetime.min.time())) - timedelta(days=1)
    dt_to = dt_from + timedelta(days=3)
    amt = _to_decimal(total_amount, DECIMAL_ZERO)
    if amt <= 0:
        return None
    low = amt * Decimal("0.99")
    high = amt * Decimal("1.01")
    inv = (
        Invoice.objects.filter(order__owner=owner, order__party=supplier, order__order_type="PURCHASE")
        .filter(created_at__gte=dt_from, created_at__lte=dt_to)
        .filter(amount__gte=low, amount__lte=high)
        .select_related("order")
        .order_by("-created_at", "-id")
        .first()
    )
    return inv.order if inv else None


def compute_draft_confidence(draft: PurchaseDraft) -> Decimal:
    if not draft:
        return Decimal("0.0")
    items = list(draft.items.all())
    if not items:
        return Decimal("0.0")

    match_scores = []
    review_penalty = Decimal("0.0")
    for it in items:
        match_scores.append(_to_decimal(it.match_confidence, Decimal("0.0")))
        if it.requires_review or not it.matched_product_id:
            review_penalty += Decimal("0.05")

    avg_match = sum(match_scores) / Decimal(str(len(match_scores))) if match_scores else Decimal("0.0")
    base = avg_match
    # Supplier & invoice metadata add confidence
    if draft.supplier_id:
        base += Decimal("0.05")
    if draft.invoice_number:
        base += Decimal("0.05")
    if draft.invoice_date:
        base += Decimal("0.03")

    base -= review_penalty
    # Validation warnings reduce confidence
    try:
        warn_cnt = len(draft.validation_warnings or [])
    except Exception:
        warn_cnt = 0
    base -= Decimal("0.03") * Decimal(str(min(warn_cnt, 5)))

    if base < 0:
        base = Decimal("0.0")
    if base > 1:
        base = Decimal("1.0")
    return base.quantize(Decimal("0.001"))


def create_purchase_draft_from_parsed(
    *,
    owner,
    parsed: dict[str, Any],
    source: Optional[InvoiceSource] = None,
) -> PurchaseDraft:
    supplier_name = str(parsed.get("supplier_name") or parsed.get("supplier") or "").strip()
    invoice_no = str(parsed.get("invoice_no") or parsed.get("invoice_number") or "").strip()
    invoice_date = _parse_date(parsed.get("invoice_date"))

    supplier_party = None
    if supplier_name:
        supplier_party = Party.objects.filter(owner=owner, party_type="supplier", name__iexact=supplier_name).first()

    totals = parsed.get("totals") or {}
    if not isinstance(totals, dict):
        totals = {}
    gst_rate = _to_decimal(totals.get("gst_rate") or totals.get("tax_percent") or 0, DECIMAL_ZERO)

    draft = PurchaseDraft.objects.create(
        owner=owner,
        source=source,
        supplier_name=supplier_name[:200],
        supplier=supplier_party,
        invoice_number=invoice_no[:80],
        invoice_date=invoice_date,
        gst_rate=gst_rate.quantize(Decimal("0.01")) if gst_rate > 0 else Decimal("0.00"),
        status=PurchaseDraft.Status.EXTRACTED,
    )

    items = parsed.get("items") or []
    if not isinstance(items, list):
        items = []

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("product") or "").strip()
        qty = _to_decimal(item.get("qty") or 0, DECIMAL_ZERO)
        unit = str(item.get("unit") or "").strip()
        rate = _to_decimal(item.get("rate") or 0, DECIMAL_ZERO)
        gst_rate = _to_decimal(item.get("gst_rate") or item.get("tax_percent") or 0, DECIMAL_ZERO)
        amount = _to_decimal(item.get("amount") or 0, DECIMAL_ZERO)
        if amount <= 0 and qty > 0 and rate > 0:
            amount = (qty * rate).quantize(Decimal("0.01"))

        PurchaseDraftItem.objects.create(
            draft=draft,
            line_no=idx,
            raw_name=name[:200],
            quantity=qty.quantize(Decimal("0.001")),
            unit=unit[:30],
            rate=rate.quantize(Decimal("0.01")),
            gst_rate=gst_rate.quantize(Decimal("0.01")),
            amount=amount.quantize(Decimal("0.01")),
        )

    draft.recompute_totals(save=True)
    return draft


def process_purchase_draft(
    *,
    draft: PurchaseDraft,
    auto_mode: bool = True,
    auto_approve_threshold: Decimal = Decimal("0.92"),
    product_match_threshold: Decimal = Decimal("0.82"),
) -> PurchaseDraft:
    if not draft:
        raise ValueError("draft is required")

    # Supplier identification
    if not draft.supplier_id and draft.supplier_name:
        draft.supplier = get_or_create_supplier(draft.owner, draft.supplier_name)
        draft.save(update_fields=["supplier", "updated_at"])

    apply_supplier_template_to_draft(draft)

    # Product matching
    for it in draft.items.select_related("matched_product").all():
        m = _best_product_match(draft.owner, draft.supplier, it.raw_name, threshold=product_match_threshold)
        it.matched_product = m.product
        it.match_confidence = m.confidence
        it.match_method = m.method
        it.requires_review = (m.product is None) or (m.confidence < product_match_threshold)
        it.save(update_fields=["matched_product", "match_confidence", "match_method", "requires_review"])

    normalize_units_for_draft(draft)

    # Validation: duplicate invoice
    warnings: list[dict[str, Any]] = []
    dup = detect_duplicate_purchase_invoice(
        owner=draft.owner,
        supplier=draft.supplier,
        invoice_number=draft.invoice_number,
        invoice_date=draft.invoice_date,
        total_amount=_to_decimal(draft.total_amount, DECIMAL_ZERO),
    )
    if dup:
        warnings.append(
            {
                "type": "duplicate_invoice",
                "message": "Potential duplicate purchase invoice detected",
                "reference": {"type": "commerce.Order", "id": dup.id},
            }
        )

    # GST best-effort: if draft GST missing, infer max from items.
    if _to_decimal(draft.gst_rate, DECIMAL_ZERO) <= 0:
        best = DECIMAL_ZERO
        for it in draft.items.all():
            best = max(best, _to_decimal(it.gst_rate, DECIMAL_ZERO))
        if best > 0:
            draft.gst_rate = best.quantize(Decimal("0.01"))
            draft.save(update_fields=["gst_rate", "updated_at"])

    # Price consistency check against SupplierProduct master (if present)
    if draft.supplier_id:
        threshold_pct = Decimal("25.0")
        for it in draft.items.select_related("matched_product").all():
            if not it.matched_product_id:
                continue
            base_price = (
                SupplierProduct.objects.filter(
                    owner=draft.owner,
                    supplier_id=draft.supplier_id,
                    product_id=it.matched_product_id,
                    is_active=True,
                )
                .values_list("price", flat=True)
                .first()
            )
            base_price = _to_decimal(base_price, DECIMAL_ZERO)
            rate = _to_decimal(it.rate, DECIMAL_ZERO)
            if base_price <= 0 or rate <= 0:
                continue
            try:
                change = ((rate - base_price) / base_price) * Decimal("100")
            except Exception:
                continue
            if abs(change) >= threshold_pct:
                warnings.append(
                    {
                        "type": "price_anomaly",
                        "message": "Purchase rate deviates from supplier master price",
                        "item": {
                            "draft_item_id": it.id,
                            "product_id": it.matched_product_id,
                            "base_price": str(base_price.quantize(Decimal('0.01'))),
                            "invoice_rate": str(rate.quantize(Decimal('0.01'))),
                            "change_pct": str(change.quantize(Decimal('0.01'))),
                        },
                    }
                )

    # GST sanity
    if draft.gst_rate and (draft.gst_rate < 0 or draft.gst_rate > 100):
        warnings.append({"type": "gst_invalid", "message": "GST rate out of range"})

    draft.validation_warnings = warnings
    draft.status = PurchaseDraft.Status.VALIDATED if warnings else PurchaseDraft.Status.READY
    draft.confidence = compute_draft_confidence(draft)
    draft.save(update_fields=["validation_warnings", "status", "confidence", "updated_at"])

    if warnings and any(w.get("type") == "duplicate_invoice" for w in warnings):
        # Never auto-approve duplicates.
        return draft

    if auto_mode and draft.confidence >= auto_approve_threshold and draft.status in {PurchaseDraft.Status.READY, PurchaseDraft.Status.VALIDATED}:
        try:
            approve_purchase_draft(draft=draft, auto_approved=True)
        except Exception:
            logger.exception("Auto-approval failed for draft %s", draft.id)
    return draft


def _qty_decimal_to_int(qty: Decimal) -> int:
    q = _to_decimal(qty, Decimal("0"))
    if q <= 0:
        return 1
    try:
        if q == q.to_integral_value():
            return int(q)
    except Exception:
        pass
    if q < 1:
        return 1
    try:
        return int(q.to_integral_value(rounding=ROUND_HALF_UP))
    except Exception:
        return max(int(q), 1)


@transaction.atomic
def approve_purchase_draft(*, draft: PurchaseDraft, auto_approved: bool = False, approved_by=None) -> Order:
    if not draft:
        raise ValueError("draft is required")
    if draft.created_order_id:
        # Idempotent: already approved/posted.
        return draft.created_order

    # Lock draft row to avoid double-post.
    locked = PurchaseDraft.objects.select_for_update().select_related("supplier", "source").get(id=draft.id)
    if locked.created_order_id:
        return locked.created_order

    supplier = locked.supplier or get_or_create_supplier(locked.owner, locked.supplier_name)
    source_type = getattr(getattr(locked.source, "source_type", None), "value", None) or getattr(locked.source, "source_type", "") or "manual"

    order = Order.objects.create(
        owner=locked.owner,
        party=supplier,
        order_type="PURCHASE",
        status="completed",
        invoice_number=(locked.invoice_number or None),
        notes="Created by AR-CSSPS Purchase Automation",
        order_source=str(source_type)[:30] or "Automation",
        tax_percent=_to_decimal(locked.gst_rate, DECIMAL_ZERO),
    )

    rounding_warnings = []
    for it in locked.items.select_related("matched_product").all().order_by("line_no", "id"):
        qty_src = _to_decimal(it.normalized_quantity or it.quantity, DECIMAL_ZERO)
        qty_int = _qty_decimal_to_int(qty_src)
        if qty_src != Decimal(str(qty_int)):
            rounding_warnings.append({"item_id": it.id, "from": str(qty_src), "to": str(qty_int)})

        rate = _to_decimal(it.rate, DECIMAL_ZERO).quantize(Decimal("0.01"))
        gst = _to_decimal(it.gst_rate, _to_decimal(locked.gst_rate, DECIMAL_ZERO)).quantize(Decimal("0.01"))
        raw_name = (it.raw_name or "").strip()

        OrderItem.objects.create(
            order=order,
            product=it.matched_product,
            raw_name=raw_name[:200],
            qty=qty_int,
            price=rate,
            tax_percent=gst,
        )

    order.save()
    invoice = Invoice.objects.create(order=order, gst_type=("GST" if _to_decimal(locked.gst_rate, DECIMAL_ZERO) > 0 else "NON_GST"))

    # Self-learning: persist high-confidence supplier product aliases.
    try:
        if supplier and supplier.party_type == "supplier":
            for it in locked.items.select_related("matched_product").all():
                if not it.matched_product_id:
                    continue
                conf = _to_decimal(it.match_confidence, Decimal("0.0"))
                if conf < Decimal("0.850"):
                    continue
                nm = _norm_text(it.raw_name)
                if not nm:
                    continue
                alias, created = SupplierProductAlias.objects.get_or_create(
                    owner=locked.owner,
                    supplier=supplier,
                    normalized_name=nm,
                    defaults={
                        "raw_name": (it.raw_name or "")[:200],
                        "product_id": it.matched_product_id,
                        "confidence": conf.quantize(Decimal("0.001")),
                        "times_used": 1,
                        "last_used_at": timezone.now(),
                    },
                )
                if not created:
                    SupplierProductAlias.objects.filter(id=alias.id).update(
                        raw_name=(it.raw_name or "")[:200],
                        product_id=it.matched_product_id,
                        confidence=max(_to_decimal(alias.confidence, conf), conf).quantize(Decimal("0.001")),
                        times_used=F("times_used") + 1,
                        last_used_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
    except Exception:
        logger.exception("Failed to persist supplier aliases for draft %s", locked.id)

    locked.created_order = order
    locked.auto_approved = bool(auto_approved)
    locked.status = PurchaseDraft.Status.POSTED
    if rounding_warnings:
        locked.validation_warnings = (locked.validation_warnings or []) + [{"type": "qty_rounded", "items": rounding_warnings}]
    locked.save(update_fields=["created_order", "auto_approved", "status", "validation_warnings", "updated_at"])

    invoice_rec = PurchaseInvoice.objects.create(
        owner=locked.owner,
        supplier=supplier,
        invoice_number=locked.invoice_number,
        invoice_date=locked.invoice_date,
        invoice_total=_to_decimal(invoice.amount, DECIMAL_ZERO),
        source=locked.source,
        draft=locked,
        order=order,
        status=PurchaseInvoice.Status.POSTED,
        metadata={"auto_approved": bool(auto_approved)},
    )

    for it in locked.items.select_related("matched_product").all():
        PurchaseItem.objects.create(
            purchase_invoice=invoice_rec,
            product=it.matched_product,
            raw_name=(it.raw_name or "")[:200],
            qty=_to_decimal(it.normalized_quantity or it.quantity, DECIMAL_ZERO).quantize(Decimal("0.001")),
            unit=(it.normalized_unit or it.unit or "")[:30],
            rate=_to_decimal(it.rate, DECIMAL_ZERO).quantize(Decimal("0.01")),
            gst_rate=_to_decimal(it.gst_rate, DECIMAL_ZERO).quantize(Decimal("0.01")),
            amount=_to_decimal(it.amount, DECIMAL_ZERO).quantize(Decimal("0.01")),
        )

    try:
        AITrainingLog.objects.create(
            owner=locked.owner,
            event_type=(AITrainingLog.EventType.AUTO_APPROVED if auto_approved else AITrainingLog.EventType.DRAFT_APPROVED),
            reference_type="procurement.PurchaseDraft",
            reference_id=locked.id,
            payload={
                "order_id": order.id,
                "invoice_id": invoice.id,
                "auto_approved": bool(auto_approved),
                "approved_by": getattr(approved_by, "id", None),
            },
        )
    except Exception:
        pass

    if locked.source_id:
        try:
            InvoiceSource.objects.filter(id=locked.source_id).update(
                status=InvoiceSource.Status.PROCESSED,
                reference_type="commerce.Order",
                reference_id=order.id,
                updated_at=timezone.now(),
            )
        except Exception:
            pass

    return order
