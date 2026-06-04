from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

from commerce.models import Order
from khataapp.models import Party
from whatsapp.models import WhatsAppAccount
from whatsapp.services.provider_clients import send_text

logger = logging.getLogger(__name__)


def _pick_best_account(*, owner) -> Optional[WhatsAppAccount]:
    qs = WhatsAppAccount.objects.filter(owner=owner, is_active=True)
    acc = qs.filter(status=WhatsAppAccount.Status.CONNECTED).order_by("-updated_at").first()
    return acc or qs.order_by("-updated_at").first()


def _party_phone(party: Party) -> str:
    # Prefer WhatsApp number if present, else mobile.
    for v in (getattr(party, "whatsapp_number", None), getattr(party, "mobile", None)):
        s = (str(v or "")).strip()
        if s:
            return s
    return ""


def send_supplier_payment_reminders(
    *,
    owner,
    account: Optional[WhatsAppAccount] = None,
    max_parties: int = 50,
    max_orders_per_party: int = 5,
    dry_run: bool = False,
) -> dict:
    """
    Send WhatsApp payment reminders to suppliers for overdue/dues purchase orders.

    - Groups purchase orders by supplier (Party)
    - Sends at most 1 reminder per supplier per day (cache)
    - Uses the owner's connected WhatsAppAccount (or the newest one) when not provided
    """
    account = account or _pick_best_account(owner=owner)
    if not account:
        return {"ok": False, "error": "no_whatsapp_account"}

    today = timezone.localdate()
    qs = (
        Order.objects.select_related("party")
        .filter(owner=owner, order_type="PURCHASE")
        .exclude(status__in=["cancelled", "rejected"])
        .filter(due_amount__gt=0)
        .order_by("payment_due_date", "-created_at")[:2000]
    )

    grouped: dict[int, list[Order]] = defaultdict(list)
    for o in qs:
        if not getattr(o, "party_id", None):
            continue
        grouped[int(o.party_id)].append(o)

    sent = 0
    skipped = 0
    failed = 0
    parties_processed = 0

    for party_id, orders in list(grouped.items())[: max(1, int(max_parties or 50))]:
        parties_processed += 1
        party = orders[0].party
        phone = _party_phone(party)
        if not phone:
            skipped += 1
            continue

        cache_key = f"wa:sup_due:{account.id}:{party_id}:{today.isoformat()}"
        if not cache.add(cache_key, 1, timeout=26 * 60 * 60):
            skipped += 1
            continue

        total_due = Decimal("0.00")
        overdue_count = 0
        lines = []
        for o in orders[: max(1, int(max_orders_per_party or 5))]:
            due = Decimal(str(getattr(o, "due_amount", 0) or 0))
            if due <= 0:
                continue
            total_due += due
            dd = getattr(o, "payment_due_date", None)
            if dd and dd < today:
                overdue_count += 1
            inv = (getattr(o, "invoice_number", "") or "").strip()
            inv_txt = f"#{inv}" if inv else f"Order {o.id}"
            dd_txt = f" due {dd}" if dd else ""
            lines.append(f"- {inv_txt}: ₹{due}{dd_txt}")

        if not lines:
            skipped += 1
            continue

        msg = (
            f"Payment Reminder\n"
            f"{party.name} ji, aapka total pending: ₹{total_due}\n"
            + ("\n".join(lines))
            + (f"\nOverdue bills: {overdue_count}" if overdue_count else "")
            + "\n\nPlease confirm payment date. धन्यवाद"
        )

        if dry_run:
            sent += 1
            continue

        try:
            res = send_text(account=account, to=phone, text=msg)
            if res.ok:
                sent += 1
            else:
                failed += 1
                logger.warning("Supplier reminder failed: %s", (res.response_text or "")[:200])
        except Exception:
            failed += 1
            logger.exception("Supplier reminder send error")

    return {
        "ok": True,
        "account_id": str(account.id),
        "date": str(today),
        "parties": parties_processed,
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
    }

