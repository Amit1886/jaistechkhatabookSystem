from decimal import Decimal

from django.db.models import DecimalField, F, Sum
from django.utils.timezone import now

from accounts.models import BusinessSnapshot
from commerce.models import Invoice, Order, OrderItem, Payment
from khataapp.models import Transaction, Party


def build_business_snapshot(user, date=None):
    date = date or now().date()

    snapshot, _ = BusinessSnapshot.objects.get_or_create(
        user=user,
        date=date
    )

    # ====
    # 🔹 SALES
    # ====
    money_field = DecimalField(max_digits=14, decimal_places=2)

    sales_qs = Order.objects.filter(owner=user, created_at__date=date, order_type="SALE")
    snapshot.sales_orders = sales_qs.count()
    sales_items_total = (
        OrderItem.objects.filter(order__in=sales_qs)
        .aggregate(t=Sum(F("qty") * F("price"), output_field=money_field))["t"]
        or Decimal("0.00")
    )
    sales_discount = sales_qs.aggregate(t=Sum("discount_amount"))["t"] or Decimal("0.00")
    sales_tax = sales_qs.aggregate(t=Sum("tax_amount"))["t"] or Decimal("0.00")
    sales_bill_sundry = sum((o.bill_sundry_total() for o in sales_qs.only("bill_sundry")), Decimal("0.00"))
    snapshot.sales_amount = sales_items_total - sales_discount + sales_tax + sales_bill_sundry

    # ====
    # 🔹 PURCHASE
    # ====
    purchase_qs = Order.objects.filter(owner=user, created_at__date=date, order_type="PURCHASE")
    snapshot.purchase_orders = purchase_qs.count()
    purchase_items_total = (
        OrderItem.objects.filter(order__in=purchase_qs)
        .aggregate(t=Sum(F("qty") * F("price"), output_field=money_field))["t"]
        or Decimal("0.00")
    )
    purchase_discount = purchase_qs.aggregate(t=Sum("discount_amount"))["t"] or Decimal("0.00")
    purchase_tax = purchase_qs.aggregate(t=Sum("tax_amount"))["t"] or Decimal("0.00")
    purchase_bill_sundry = sum((o.bill_sundry_total() for o in purchase_qs.only("bill_sundry")), Decimal("0.00"))
    snapshot.purchase_amount = purchase_items_total - purchase_discount + purchase_tax + purchase_bill_sundry

    # ====
    # 🔹 PAYMENTS
    # ====
    snapshot.payment_received = (
        Payment.objects.filter(created_at__date=date, invoice__order__owner=user, invoice__order__order_type="SALE")
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )

    snapshot.payment_given = (
        Payment.objects.filter(created_at__date=date, invoice__order__owner=user, invoice__order__order_type="PURCHASE")
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )

    # ====
    # 🔹 RECEIVABLE (Customer se lena)
    # ====
    snapshot.receivable_amount = (
        Invoice.objects.filter(order__owner=user, order__order_type="SALE", status="unpaid")
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )

    # ====
    # 🔹 PAYABLE (Supplier ko dena)
    # ====
    snapshot.payable_amount = (
        Invoice.objects.filter(order__owner=user, order__order_type="PURCHASE", status="unpaid")
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )

    snapshot.net_position = (
        snapshot.receivable_amount - snapshot.payable_amount
    )

    # ====
    # 🔹 COUNTS
    # ====
    snapshot.total_parties = Party.objects.filter(owner=user).count()

    snapshot.total_transactions = Transaction.objects.filter(party__owner=user, date=date).count()

    snapshot.save()
    return snapshot
