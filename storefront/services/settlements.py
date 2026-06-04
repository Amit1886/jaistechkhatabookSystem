from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from wallet.models import WalletTransaction
from wallet.services import get_or_create_wallet

from storefront.models import PlatformSettings, StoreOrder, StoreSettlement


def get_platform_settings() -> PlatformSettings:
    obj = PlatformSettings.objects.order_by("id").first()
    if obj:
        return obj
    return PlatformSettings.objects.create(commission_percent=Decimal("0.00"))


def _quantize(amount: Decimal) -> Decimal:
    try:
        return Decimal(str(amount or "0")).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


@transaction.atomic
def settle_paid_order(*, order: StoreOrder) -> StoreSettlement:
    """
    Auto settlement:
    - commission = order.total_amount * commission_percent
    - vendor_amount = total - commission
    Credits:
    - vendor owner wallet (vendor_amount)
    - platform wallet user (commission_amount) if configured

    Idempotent via StoreSettlement(order=OneToOne).
    """
    settlement, created = StoreSettlement.objects.get_or_create(order=order)
    if settlement.status == StoreSettlement.Status.SETTLED:
        return settlement

    settings_obj = get_platform_settings()
    commission_percent = _quantize(settings_obj.commission_percent)
    total = _quantize(order.total_amount)
    commission_amount = _quantize((total * commission_percent) / Decimal("100"))
    vendor_amount = _quantize(total - commission_amount)

    settlement.commission_percent = commission_percent
    settlement.commission_amount = commission_amount
    settlement.vendor_amount = vendor_amount

    try:
        # Credit vendor wallet
        vendor_user = order.vendor.owner
        vendor_wallet = get_or_create_wallet(vendor_user)
        vendor_wallet.balance = _quantize((vendor_wallet.balance or Decimal("0.00")) + vendor_amount)
        vendor_wallet.save(update_fields=["balance", "updated_at"])
        vendor_txn = WalletTransaction.objects.create(
            wallet=vendor_wallet,
            entry_type=WalletTransaction.EntryType.CREDIT,
            amount=vendor_amount,
            source="storefront_settlement",
            reference=order.order_number,
            metadata={"order_id": order.id, "vendor_id": order.vendor_id, "commission_amount": str(commission_amount)},
        )
        settlement.vendor_wallet_txn_id = vendor_txn.id

        # Credit platform wallet (commission) if configured
        if settings_obj.platform_user and commission_amount > 0:
            platform_wallet = get_or_create_wallet(settings_obj.platform_user)
            platform_wallet.balance = _quantize((platform_wallet.balance or Decimal("0.00")) + commission_amount)
            platform_wallet.save(update_fields=["balance", "updated_at"])
            platform_txn = WalletTransaction.objects.create(
                wallet=platform_wallet,
                entry_type=WalletTransaction.EntryType.CREDIT,
                amount=commission_amount,
                source="storefront_commission",
                reference=order.order_number,
                metadata={"order_id": order.id, "vendor_id": order.vendor_id, "commission_percent": str(commission_percent)},
            )
            settlement.platform_wallet_txn_id = platform_txn.id

        settlement.status = StoreSettlement.Status.SETTLED
        settlement.error = ""
    except Exception as exc:
        settlement.status = StoreSettlement.Status.FAILED
        settlement.error = str(exc)[:255]

    settlement.save(
        update_fields=[
            "status",
            "commission_percent",
            "commission_amount",
            "vendor_amount",
            "vendor_wallet_txn_id",
            "platform_wallet_txn_id",
            "error",
            "payload",
            "updated_at",
        ]
    )
    return settlement

