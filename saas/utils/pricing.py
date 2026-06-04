from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class PriceQuote:
    unit_price: Decimal
    mrp: Optional[Decimal]
    is_b2b: bool
    moq: int
    applied_tier: str


def resolve_store_type(user) -> str:
    """
    Returns: 'b2b' | 'b2c' | 'hybrid'
    """
    store_type = (getattr(user, "store_type", "") or "").strip().lower()
    return store_type if store_type in {"b2b", "b2c", "hybrid"} else "hybrid"


def quote_price(
    *,
    base_b2c_price: Decimal,
    base_b2b_price: Optional[Decimal],
    qty: int,
    moq: int,
    is_b2b_only: bool,
    user_store_type: str,
    bulk_price: Optional[Decimal] = None,
    bulk_qty: int = 0,
    mrp: Optional[Decimal] = None,
) -> PriceQuote:
    qty = int(qty or 0)
    moq = int(moq or 0)
    bulk_qty = int(bulk_qty or 0)

    is_b2b_user = user_store_type in {"b2b", "hybrid"} and (user_store_type != "b2c")
    if is_b2b_only and not is_b2b_user:
        # Caller should hide product; pricing still returns a value.
        return PriceQuote(unit_price=base_b2c_price, mrp=mrp, is_b2b=False, moq=moq, applied_tier="blocked")

    if is_b2b_user and base_b2b_price is not None:
        # B2B price with optional bulk tier.
        if bulk_price is not None and bulk_qty and qty >= bulk_qty:
            return PriceQuote(unit_price=bulk_price, mrp=mrp, is_b2b=True, moq=moq, applied_tier=f"bulk_{bulk_qty}+")
        return PriceQuote(unit_price=base_b2b_price, mrp=mrp, is_b2b=True, moq=moq, applied_tier="b2b")

    # Default: B2C
    return PriceQuote(unit_price=base_b2c_price, mrp=mrp, is_b2b=False, moq=moq, applied_tier="b2c")

