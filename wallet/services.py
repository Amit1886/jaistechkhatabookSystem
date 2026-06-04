from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from wallet.models import Wallet, WalletTransaction, WithdrawRequest


def get_or_create_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def credit(user, amount: Decimal, *, source: str = "manual", reference: str = "", metadata=None):
    wallet = get_or_create_wallet(user)
    wallet.balance = (wallet.balance or Decimal("0.00")) + amount
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(
        wallet=wallet,
        entry_type=WalletTransaction.EntryType.CREDIT,
        amount=amount,
        source=source,
        reference=reference,
        metadata=metadata or {},
    )
    return wallet


@transaction.atomic
def debit(user, amount: Decimal, *, source: str = "manual", reference: str = "", metadata=None):
    wallet = get_or_create_wallet(user)
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance")
    wallet.balance = wallet.balance - amount
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(
        wallet=wallet,
        entry_type=WalletTransaction.EntryType.DEBIT,
        amount=amount,
        source=source,
        reference=reference,
        metadata=metadata or {},
    )
    return wallet


@transaction.atomic
def request_withdrawal(user, amount: Decimal, metadata=None) -> WithdrawRequest:
    wallet = get_or_create_wallet(user)
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance")
    wallet.balance -= amount
    wallet.save(update_fields=["balance", "updated_at"])
    return WithdrawRequest.objects.create(wallet=wallet, user=user, amount=amount, metadata=metadata or {})


@transaction.atomic
def approve_withdrawal(request_obj: WithdrawRequest, *, approver, payout_reference: str = ""):
    if request_obj.status != WithdrawRequest.Status.PENDING:
        return request_obj
    request_obj.status = WithdrawRequest.Status.APPROVED
    request_obj.processed_at = timezone.now()
    request_obj.processed_by = approver
    request_obj.payout_reference = payout_reference[:120]
    request_obj.save(update_fields=["status", "processed_at", "processed_by", "payout_reference"])
    return request_obj


@transaction.atomic
def mark_withdrawal_paid(request_obj: WithdrawRequest, *, payout_reference: str = ""):
    request_obj.status = WithdrawRequest.Status.PAID
    request_obj.payout_reference = payout_reference[:120] or request_obj.payout_reference
    request_obj.processed_at = timezone.now()
    request_obj.save(update_fields=["status", "processed_at", "payout_reference"])
    return request_obj

