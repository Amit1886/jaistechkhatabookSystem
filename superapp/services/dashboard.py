from __future__ import annotations

from decimal import Decimal

from superapp.models import CustomerWallet, SuperDashboardSnapshot, TableOrder, TaxAlert


def build_super_dashboard_snapshot(*, business_unit=None, period: str = "today"):
    wallet_liability = CustomerWallet.objects.all()
    if business_unit:
        wallet_liability = wallet_liability.filter(business_unit=business_unit)
    liability = Decimal("0.00")
    for wallet in wallet_liability.only("cashback_balance", "referral_balance", "gift_balance", "promo_balance", "store_credit", "loyalty_balance"):
        liability += wallet.usable_balance
    snapshot = SuperDashboardSnapshot.objects.create(
        business_unit=business_unit,
        period=period,
        wallet_liability=liability,
        tax_alerts=TaxAlert.objects.filter(resolved_at__isnull=True).count(),
        restaurant_open_orders=TableOrder.objects.exclude(status__in=["served", "cancelled", "paid"]).count(),
        payload={
            "wallet_liability": str(liability),
            "tax_alerts_open": TaxAlert.objects.filter(resolved_at__isnull=True).count(),
            "restaurant_open_orders": TableOrder.objects.exclude(status__in=["served", "cancelled", "paid"]).count(),
        },
    )
    return snapshot

