from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from superapp.models import CashbackRule, CustomerWallet, RewardPoint, WalletTransaction


BUCKET_FIELD = {
    WalletTransaction.Bucket.CASHBACK: "cashback_balance",
    WalletTransaction.Bucket.REFERRAL: "referral_balance",
    WalletTransaction.Bucket.GIFT: "gift_balance",
    WalletTransaction.Bucket.PROMO: "promo_balance",
    WalletTransaction.Bucket.STORE_CREDIT: "store_credit",
    WalletTransaction.Bucket.LOYALTY: "loyalty_balance",
}


def get_wallet(customer) -> CustomerWallet:
    wallet, _ = CustomerWallet.objects.get_or_create(customer=customer)
    return wallet


@transaction.atomic
def post_wallet_entry(customer, amount: Decimal, *, bucket: str, entry_type: str, source: str, channel: str = "pos", reference: str = "", metadata=None, points: int = 0):
    wallet = CustomerWallet.objects.select_for_update().get(pk=get_wallet(customer).pk)
    if wallet.is_locked:
        raise ValueError("Wallet is locked")

    amount = Decimal(str(amount or "0"))
    field = BUCKET_FIELD.get(bucket)
    if field:
        current = getattr(wallet, field) or Decimal("0.00")
        if entry_type == WalletTransaction.EntryType.DEBIT:
            if current < amount:
                raise ValueError("Insufficient wallet balance")
            setattr(wallet, field, current - amount)
        else:
            setattr(wallet, field, current + amount)

    if points:
        if entry_type == WalletTransaction.EntryType.DEBIT:
            if wallet.reward_points < abs(points):
                raise ValueError("Insufficient reward points")
            wallet.reward_points -= abs(points)
        else:
            wallet.reward_points += abs(points)
        RewardPoint.objects.create(wallet=wallet, points=points, reason=source, reference=reference, metadata=metadata or {})

    wallet.save()
    WalletTransaction.objects.create(
        wallet=wallet,
        entry_type=entry_type,
        bucket=bucket,
        amount=amount,
        points=points,
        channel=channel,
        source=source,
        reference=reference,
        metadata=metadata or {},
    )
    return wallet


def calculate_cashback(amount: Decimal, *, channel: str = "", tier: str = "") -> Decimal:
    amount = Decimal(str(amount or "0"))
    rules = CashbackRule.objects.filter(is_active=True, min_order_amount__lte=amount).order_by("-cashback_percent", "-min_order_amount")
    for rule in rules:
        if not rule.is_valid_now():
            continue
        if rule.channel and rule.channel != channel:
            continue
        if rule.tier and rule.tier != tier:
            continue
        cashback = (amount * rule.cashback_percent / Decimal("100")).quantize(Decimal("0.01"))
        if rule.max_cashback and cashback > rule.max_cashback:
            cashback = rule.max_cashback
        return cashback
    return Decimal("0.00")


@transaction.atomic
def apply_wallet_payment(customer, amount: Decimal, *, channel: str, reference: str = "", metadata=None):
    return post_wallet_entry(
        customer,
        amount,
        bucket=WalletTransaction.Bucket.STORE_CREDIT,
        entry_type=WalletTransaction.EntryType.DEBIT,
        source="checkout_redeem",
        channel=channel,
        reference=reference,
        metadata=metadata,
    )


def calculate_emi(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    principal = Decimal(str(principal or "0"))
    annual_rate = Decimal(str(annual_rate or "0"))
    months = max(int(months or 1), 1)
    monthly_rate = annual_rate / Decimal("1200")
    if monthly_rate == 0:
        return (principal / months).quantize(Decimal("0.01"))
    numerator = principal * monthly_rate * ((1 + monthly_rate) ** months)
    denominator = ((1 + monthly_rate) ** months) - 1
    return (numerator / denominator).quantize(Decimal("0.01"))

