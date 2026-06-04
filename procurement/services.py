from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Value
from django.db.models.functions import Coalesce

from procurement.models import SupplierProduct, SupplierRating


DECIMAL_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class SupplierOptionScore:
    supplier_product_id: int
    supplier_id: int
    supplier_name: str
    price: Decimal
    moq: int
    delivery_days: int
    last_updated: Any
    avg_rating: Decimal
    rating_count: int
    score_total: Decimal
    score_price: Decimal
    score_delivery: Decimal
    score_rating: Decimal


def _to_decimal(val: Any, default: Decimal = DECIMAL_ZERO) -> Decimal:
    if val is None:
        return default
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return default


def _normalize_weights(
    price_weight: Decimal | None,
    delivery_weight: Decimal | None,
    rating_weight: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal]:
    pw = _to_decimal(price_weight, Decimal("0.60"))
    dw = _to_decimal(delivery_weight, Decimal("0.20"))
    rw = _to_decimal(rating_weight, Decimal("0.20"))
    total = pw + dw + rw
    if total <= 0:
        return Decimal("0.60"), Decimal("0.20"), Decimal("0.20")
    return (pw / total, dw / total, rw / total)


def supplier_ratings_map(owner, supplier_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not supplier_ids:
        return {}

    rows = (
        SupplierRating.objects.filter(owner=owner, supplier_id__in=supplier_ids)
        .values("supplier_id")
        .annotate(
            avg_delivery=Coalesce(Avg("delivery_speed"), Value(0.0)),
            avg_quality=Coalesce(Avg("product_quality"), Value(0.0)),
            avg_pricing=Coalesce(Avg("pricing"), Value(0.0)),
            cnt=Coalesce(Count("id"), Value(0)),
        )
    )
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        supplier_id = int(r["supplier_id"])
        avg_delivery = _to_decimal(r.get("avg_delivery"), DECIMAL_ZERO)
        avg_quality = _to_decimal(r.get("avg_quality"), DECIMAL_ZERO)
        avg_pricing = _to_decimal(r.get("avg_pricing"), DECIMAL_ZERO)
        cnt = int(r.get("cnt") or 0)
        avg_rating = (avg_delivery + avg_quality + avg_pricing) / Decimal("3") if cnt else DECIMAL_ZERO
        out[supplier_id] = {"avg": avg_rating, "count": cnt}
    return out


def rank_suppliers_for_product(
    *,
    owner,
    product_id: int,
    price_weight: Decimal | None = None,
    delivery_weight: Decimal | None = None,
    rating_weight: Decimal | None = None,
) -> list[SupplierOptionScore]:
    pw, dw, rw = _normalize_weights(price_weight, delivery_weight, rating_weight)

    qs = (
        SupplierProduct.objects.filter(owner=owner, product_id=product_id, is_active=True)
        .select_related("supplier", "product")
        .filter(supplier__party_type="supplier")
    )
    options = list(qs)
    if not options:
        return []

    supplier_ids = [int(o.supplier_id) for o in options]
    rating_map = supplier_ratings_map(owner, supplier_ids)

    prices = [_to_decimal(o.price) for o in options if _to_decimal(o.price) > 0]
    deliveries = [int(o.delivery_days or 0) for o in options if int(o.delivery_days or 0) > 0]
    min_price = min(prices) if prices else DECIMAL_ZERO
    min_delivery = min(deliveries) if deliveries else 0

    scored: list[SupplierOptionScore] = []
    for opt in options:
        price = _to_decimal(opt.price)
        delivery_days = int(opt.delivery_days or 0)

        price_score = (min_price / price) if (price and price > 0 and min_price > 0) else DECIMAL_ZERO
        if price_score > 1:
            price_score = Decimal("1.00")

        delivery_score = (
            Decimal(str(min_delivery)) / Decimal(str(delivery_days))
            if (delivery_days and delivery_days > 0 and min_delivery > 0)
            else DECIMAL_ZERO
        )
        if delivery_score > 1:
            delivery_score = Decimal("1.00")

        rating_info = rating_map.get(int(opt.supplier_id), {})
        avg_rating = _to_decimal(rating_info.get("avg"))
        rating_count = int(rating_info.get("count") or 0)
        rating_score = (avg_rating / Decimal("5.0")) if avg_rating and avg_rating > 0 else DECIMAL_ZERO
        if rating_score > 1:
            rating_score = Decimal("1.00")

        total = (pw * price_score) + (dw * delivery_score) + (rw * rating_score)

        scored.append(
            SupplierOptionScore(
                supplier_product_id=int(opt.id),
                supplier_id=int(opt.supplier_id),
                supplier_name=str(getattr(opt.supplier, "name", "Supplier") or "Supplier"),
                price=price,
                moq=int(opt.moq or 1),
                delivery_days=delivery_days,
                last_updated=getattr(opt, "last_updated", None),
                avg_rating=avg_rating.quantize(Decimal("0.01")) if avg_rating else DECIMAL_ZERO,
                rating_count=rating_count,
                score_total=total.quantize(Decimal("0.0001")),
                score_price=price_score.quantize(Decimal("0.0001")),
                score_delivery=delivery_score.quantize(Decimal("0.0001")),
                score_rating=rating_score.quantize(Decimal("0.0001")),
            )
        )

    scored.sort(key=lambda x: (x.score_total, x.score_price, x.score_delivery, x.avg_rating), reverse=True)
    return scored


def best_supplier_for_product(
    *,
    owner,
    product_id: int,
    price_weight: Decimal | None = None,
    delivery_weight: Decimal | None = None,
    rating_weight: Decimal | None = None,
) -> SupplierOptionScore | None:
    ranked = rank_suppliers_for_product(
        owner=owner,
        product_id=product_id,
        price_weight=price_weight,
        delivery_weight=delivery_weight,
        rating_weight=rating_weight,
    )
    return ranked[0] if ranked else None


def best_supplier_map_for_products(owner, product_ids: list[int]) -> dict[int, SupplierOptionScore]:
    """
    Efficiently compute best supplier per product.
    """
    if not product_ids:
        return {}

    qs = (
        SupplierProduct.objects.filter(owner=owner, product_id__in=product_ids, is_active=True)
        .select_related("supplier", "product")
        .filter(supplier__party_type="supplier")
    )
    items = list(qs)
    if not items:
        return {}

    supplier_ids = list({int(i.supplier_id) for i in items})
    rating_map = supplier_ratings_map(owner, supplier_ids)

    grouped: dict[int, list[SupplierProduct]] = defaultdict(list)
    for it in items:
        grouped[int(it.product_id)].append(it)

    out: dict[int, SupplierOptionScore] = {}
    pw, dw, rw = _normalize_weights(None, None, None)

    for product_id, opts in grouped.items():
        prices = [_to_decimal(o.price) for o in opts if _to_decimal(o.price) > 0]
        deliveries = [int(o.delivery_days or 0) for o in opts if int(o.delivery_days or 0) > 0]
        min_price = min(prices) if prices else DECIMAL_ZERO
        min_delivery = min(deliveries) if deliveries else 0

        best: SupplierOptionScore | None = None
        for opt in opts:
            price = _to_decimal(opt.price)
            delivery_days = int(opt.delivery_days or 0)

            price_score = (min_price / price) if (price and price > 0 and min_price > 0) else DECIMAL_ZERO
            if price_score > 1:
                price_score = Decimal("1.00")

            delivery_score = (
                Decimal(str(min_delivery)) / Decimal(str(delivery_days))
                if (delivery_days and delivery_days > 0 and min_delivery > 0)
                else DECIMAL_ZERO
            )
            if delivery_score > 1:
                delivery_score = Decimal("1.00")

            rating_info = rating_map.get(int(opt.supplier_id), {})
            avg_rating = _to_decimal(rating_info.get("avg"))
            rating_count = int(rating_info.get("count") or 0)
            rating_score = (avg_rating / Decimal("5.0")) if avg_rating and avg_rating > 0 else DECIMAL_ZERO
            if rating_score > 1:
                rating_score = Decimal("1.00")

            total = (pw * price_score) + (dw * delivery_score) + (rw * rating_score)
            candidate = SupplierOptionScore(
                supplier_product_id=int(opt.id),
                supplier_id=int(opt.supplier_id),
                supplier_name=str(getattr(opt.supplier, "name", "Supplier") or "Supplier"),
                price=price,
                moq=int(opt.moq or 1),
                delivery_days=delivery_days,
                last_updated=getattr(opt, "last_updated", None),
                avg_rating=avg_rating.quantize(Decimal("0.01")) if avg_rating else DECIMAL_ZERO,
                rating_count=rating_count,
                score_total=total.quantize(Decimal("0.0001")),
                score_price=price_score.quantize(Decimal("0.0001")),
                score_delivery=delivery_score.quantize(Decimal("0.0001")),
                score_rating=rating_score.quantize(Decimal("0.0001")),
            )

            if best is None or candidate.score_total > best.score_total:
                best = candidate

        if best is not None:
            out[int(product_id)] = best

    return out
