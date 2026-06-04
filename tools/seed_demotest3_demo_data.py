import os
import random
import string
import sys
from datetime import timedelta
from decimal import Decimal

import django

# ensure project root on path
sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import LedgerEntry as PartyLedgerEntry
from commerce.models import Category, Order, OrderItem, Product
from khataapp.models import CreditAccount, Party
from ledger.models import LedgerEntry as GLEntry
from ledger.models import LedgerTransaction
from ledger.services.posting import get_or_create_system_account


User = get_user_model()


def _rand_mobile() -> str:
    return "9" + "".join(random.choice(string.digits) for _ in range(9))


def _rand_sku() -> str:
    return "SKU" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))


def _ensure_parties(owner, min_count: int = 12):
    existing = list(Party.objects.filter(owner=owner).order_by("id"))
    if len(existing) >= min_count:
        return existing

    need = min_count - len(existing)
    created = []
    for i in range(need):
        created.append(
            Party.objects.create(
                owner=owner,
                name=f"Demo Party {len(existing) + i + 1}",
                mobile=_rand_mobile(),
                party_type="customer" if (i % 2 == 0) else "supplier",
                is_active=True,
            )
        )
    return existing + created


def _ensure_credit_accounts(parties):
    accounts = {}
    for p in parties:
        ca = CreditAccount.objects.filter(party=p).first()
        if not ca:
            ca = CreditAccount.objects.create(party=p, user=p.owner, credit_limit=Decimal("50000.00"), outstanding=Decimal("0.00"))
        accounts[p.id] = ca
    return accounts


def _ensure_party_ledger_entries(owner, parties, credit_accounts, min_entries: int = 60):
    qs = PartyLedgerEntry.objects.filter(party__owner=owner)
    if qs.count() >= min_entries:
        return

    remaining = max(0, min_entries - qs.count())
    now = timezone.now()

    for i in range(remaining):
        p = random.choice(parties)
        ca = credit_accounts[p.id]
        is_credit = (i % 2 == 0)
        amt = Decimal(str(random.randint(50, 5000)))
        PartyLedgerEntry.objects.create(
            account=ca,
            party=p,
            amount=amt,
            txn_type="credit" if is_credit else "debit",
            invoice_no=f"INV-{now.strftime('%y%m')}-{i+1:04d}",
            description=random.choice(
                [
                    "Sale",
                    "Payment Received",
                    "Purchase",
                    "Expense",
                    "Adjustment",
                ]
            ),
            notes="Auto-seeded demo entry",
            source="manual",
            date=now - timedelta(days=random.randint(0, 25), hours=random.randint(0, 10)),
        )


def _ensure_products(owner, min_count: int = 15):
    existing = list(Product.objects.filter(owner=owner).order_by("id"))
    if len(existing) >= min_count:
        return existing

    category = Category.objects.filter(owner=owner).first()
    if not category:
        category = Category.objects.create(owner=owner, name="General", description="Demo category")

    need = min_count - len(existing)
    created = []
    for i in range(need):
        # Ensure SKU unique (simple retry loop).
        for _ in range(10):
            sku = _rand_sku()
            if not Product.objects.filter(sku=sku).exists():
                break
        else:
            sku = f"{_rand_sku()}X"

        created.append(
            Product.objects.create(
                owner=owner,
                name=f"Demo Product {len(existing) + i + 1}",
                category=category,
                price=Decimal(str(random.randint(20, 2500))),
                stock=random.randint(5, 120),
                sku=sku,
                unit="pcs",
                gst_rate=Decimal("18.00") if (i % 3 == 0) else Decimal("0.00"),
                description="Auto-seeded demo product",
            )
        )

    return existing + created


def _ensure_orders(owner, parties, products, min_count: int = 12):
    existing = Order.objects.filter(owner=owner).count()
    if existing >= min_count:
        return

    now = timezone.now()
    for i in range(min_count - existing):
        party = random.choice(parties)
        order = Order.objects.create(
            owner=owner,
            party=party,
            placed_by="user",
            status=random.choice(["pending", "accepted", "fulfilled"]),
            order_type="SALE",
            notes="Auto-seeded demo order",
            order_source="DemoSeed",
            created_at=now - timedelta(days=random.randint(0, 20), hours=random.randint(0, 10)),
            discount_type="none",
            tax_percent=Decimal("0.00"),
        )

        for _ in range(random.randint(1, 4)):
            pr = random.choice(products)
            qty = random.randint(1, 5)
            OrderItem.objects.create(order=order, product=pr, qty=qty, price=pr.price, raw_name=pr.name)

        # re-save to compute totals after items exist
        order.save()


def _ensure_gl_transactions(owner, parties, min_count: int = 10):
    existing = LedgerTransaction.objects.filter(owner=owner).count()
    if existing >= min_count:
        return

    cash = get_or_create_system_account(owner, "CASH")
    sales = get_or_create_system_account(owner, "SALES")
    expense = get_or_create_system_account(owner, "PURCHASE")

    today = timezone.now().date()

    for i in range(min_count - existing):
        amount = Decimal(str(random.randint(200, 8000))).quantize(Decimal("0.01"))
        is_sale = (i % 2 == 0)
        vt = LedgerTransaction.VoucherType.SALES_INVOICE if is_sale else LedgerTransaction.VoucherType.EXPENSE

        txn = LedgerTransaction.objects.create(
            owner=owner,
            voucher_type=vt,
            date=today - timedelta(days=random.randint(0, 25)),
            reference_type="DEMO",
            reference_id=100000 + i + 1,
            reference_no=f"DEMO-{i+1:04d}",
            narration="Auto-seeded demo voucher",
            total_debit=amount,
            total_credit=amount,
        )

        if is_sale:
            # DR Cash, CR Sales
            GLEntry.objects.create(transaction=txn, account=cash, line_no=1, debit=amount, credit=Decimal("0.00"), description="Cash sale")
            GLEntry.objects.create(transaction=txn, account=sales, line_no=2, debit=Decimal("0.00"), credit=amount, description="Sales income")
        else:
            # DR Expense(Purchase), CR Cash
            GLEntry.objects.create(transaction=txn, account=expense, line_no=1, debit=amount, credit=Decimal("0.00"), description="Expense")
            GLEntry.objects.create(transaction=txn, account=cash, line_no=2, debit=Decimal("0.00"), credit=amount, description="Paid in cash")


def main():
    username = os.environ.get("DEMO_USERNAME") or "Demotest3"
    user = User.objects.filter(username__iexact=username).first()
    if not user:
        print(f"User {username} not found. Run tools/enable_demo_features.py first.")
        raise SystemExit(2)

    with transaction.atomic():
        parties = _ensure_parties(user, min_count=12)
        credit_accounts = _ensure_credit_accounts(parties)
        _ensure_party_ledger_entries(user, parties, credit_accounts, min_entries=60)

        products = _ensure_products(user, min_count=15)
        _ensure_orders(user, parties, products, min_count=12)

        _ensure_gl_transactions(user, parties, min_count=10)

    print("Seed complete for:", username)
    print("Now refresh:")
    print("- /accounts/ledger/")
    print("- /commerce/orders/sales/")
    print("- /commerce/add-order/")
    print("- /reports/erp/trial-balance/")


if __name__ == "__main__":
    main()

