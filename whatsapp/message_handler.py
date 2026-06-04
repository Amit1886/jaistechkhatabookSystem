from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

import uuid

from accounts.models import Expense, ExpenseCategory
from commerce.models import Invoice, Order, OrderItem, Payment, Product
from khataapp.models import Party, Transaction as KhataTransaction

from whatsapp.models import WhatsAppMessage
from whatsapp.parser import ParsedCommand, parse_accounting_command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandleResult:
    ok: bool
    reply: str
    intent: str
    reference_type: str = ""
    reference_id: Optional[int] = None


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _get_or_create_party(owner, name: str, party_type: str) -> Party:
    name = (name or "").strip() or ("Walk-in Customer" if party_type == "customer" else "Unknown Party")
    party = Party.objects.filter(owner=owner, name__iexact=name, party_type=party_type).first()
    if party:
        return party
    return Party.objects.create(owner=owner, name=name, party_type=party_type)


def _match_product(owner, name: str) -> Optional[Product]:
    name = (name or "").strip()
    if not name:
        return None
    p = Product.objects.filter(owner=owner, name__iexact=name).first()
    if p:
        return p
    # fallback: contains match
    return Product.objects.filter(owner=owner, name__icontains=name).order_by("name").first()


@transaction.atomic
def handle_inbound_message(*, owner, from_number: str, to_number: str, body: str, raw_payload: dict[str, Any] | None = None) -> HandleResult:
    body = (body or "").strip()
    msg = WhatsAppMessage.objects.create(
        owner=owner,
        direction=WhatsAppMessage.Direction.INBOUND,
        from_number=(from_number or "").strip(),
        to_number=(to_number or "").strip(),
        body=body,
        raw_payload=raw_payload or {},
        status=WhatsAppMessage.Status.RECEIVED,
    )

    parsed = parse_accounting_command(body)
    if not parsed:
        msg.status = WhatsAppMessage.Status.IGNORED
        msg.error = "Unrecognized command"
        msg.save(update_fields=["status", "error"])
        return HandleResult(ok=False, reply="Sorry, I couldn't understand. Try: sale 5 item 250 / expense diesel 500 / receive payment 5000 from Party", intent="")

    try:
        result = execute_parsed_command(owner=owner, parsed=parsed)
        msg.parsed_intent = parsed.intent
        msg.parsed_payload = parsed.payload
        msg.status = WhatsAppMessage.Status.PROCESSED if result.ok else WhatsAppMessage.Status.FAILED
        msg.reference_type = result.reference_type
        msg.reference_id = result.reference_id
        msg.error = "" if result.ok else result.reply
        msg.save(update_fields=["parsed_intent", "parsed_payload", "status", "reference_type", "reference_id", "error"])
        return result
    except Exception as e:
        logger.exception("WhatsApp command execution failed")
        msg.parsed_intent = parsed.intent
        msg.parsed_payload = parsed.payload
        msg.status = WhatsAppMessage.Status.FAILED
        msg.error = f"{type(e).__name__}: {e}"
        msg.save(update_fields=["parsed_intent", "parsed_payload", "status", "error"])
        return HandleResult(ok=False, reply="Failed to process command. Please try again or use the dashboard.", intent=parsed.intent)


def execute_parsed_command(*, owner, parsed: ParsedCommand) -> HandleResult:
    intent = parsed.intent
    payload = parsed.payload or {}

    if intent == "expense":
        amount = _to_decimal(payload.get("amount"))
        desc = str(payload.get("description") or "").strip()
        if amount <= 0:
            return HandleResult(ok=False, reply="Expense amount must be > 0", intent=intent)
        category, _ = ExpenseCategory.objects.get_or_create(
            name="WhatsApp",
            created_by=owner,
        )
        exp = Expense.objects.create(
            expense_number=f"EXP-WA-{uuid.uuid4().hex[:10].upper()}",
            expense_date=timezone.localdate(),
            category=category,
            description=desc or "WhatsApp expense",
            amount_paid=amount,
            created_by=owner,
        )
        return HandleResult(ok=True, reply=f"Expense saved: ₹{amount} ({desc or 'WhatsApp expense'})", intent=intent, reference_type="accounts.Expense", reference_id=exp.id)

    if intent == "sale":
        qty = int(payload.get("qty") or 1)
        qty = max(qty, 1)
        item_name = str(payload.get("item_name") or "").strip()
        amount = _to_decimal(payload.get("amount"))
        unit_price = _to_decimal(payload.get("unit_price"))
        if amount <= 0 and unit_price <= 0:
            return HandleResult(ok=False, reply="Sale needs an amount. Example: sale 5 ice cream 250", intent=intent)

        product = _match_product(owner, item_name)
        if not product:
            # Create a lightweight product to avoid losing entry
            product = Product.objects.create(
                owner=owner,
                name=item_name or "WhatsApp Item",
                price=unit_price if unit_price > 0 else (amount / Decimal(qty)).quantize(Decimal("0.01")),
                stock=0,
                min_stock=0,
                sku=f"WA-{uuid.uuid4().hex[:12].upper()}",
                unit="pcs",
            )

        if unit_price <= 0:
            unit_price = (amount / Decimal(qty)).quantize(Decimal("0.01"))

        party = _get_or_create_party(owner, "Walk-in Customer", "customer")
        order = Order.objects.create(
            owner=owner,
            party=party,
            order_type="SALE",
            status="completed",
            notes="Created from WhatsApp accounting command",
            order_source="WhatsApp Accounting",
        )
        OrderItem.objects.create(order=order, product=product, qty=qty, price=unit_price)
        # Recompute totals after items are created (matches main order flow).
        order.save()
        invoice = Invoice.objects.create(order=order)
        # Optional: mark paid immediately for simple WhatsApp sales
        Payment.objects.create(invoice=invoice, amount=order.total_amount(), method="WhatsApp", note="Auto payment for WhatsApp sale")
        return HandleResult(ok=True, reply=f"Sale created: Order #{order.id}, Total ₹{order.total_amount()}", intent=intent, reference_type="commerce.Order", reference_id=order.id)

    if intent in {"receive_payment", "make_payment"}:
        amount = _to_decimal(payload.get("amount"))
        party_name = str(payload.get("party_name") or "").strip()
        if amount <= 0:
            return HandleResult(ok=False, reply="Payment amount must be > 0", intent=intent)

        if party_name:
            party = Party.objects.filter(owner=owner, name__icontains=party_name).order_by("name").first()
        else:
            party = None

        if not party:
            return HandleResult(ok=False, reply="Party not found. Example: receive payment 5000 from Ram Traders", intent=intent)

        txn_type = "credit" if intent == "receive_payment" else "debit"
        txn = KhataTransaction.objects.create(
            party=party,
            txn_type=txn_type,
            txn_mode="bank",
            amount=amount,
            date=timezone.localdate(),
            notes=f"WhatsApp {intent.replace('_', ' ')}",
            voucher_type="whatsapp",
            created_by=owner,
        )
        verb = "Received" if txn_type == "credit" else "Paid"
        return HandleResult(ok=True, reply=f"{verb} ₹{amount} {'from' if txn_type == 'credit' else 'to'} {party.name}", intent=intent, reference_type="khataapp.Transaction", reference_id=txn.id)

    return HandleResult(ok=False, reply="Unsupported command", intent=intent)


# Backward-compat alias (internal callers).
_execute_command = execute_parsed_command
