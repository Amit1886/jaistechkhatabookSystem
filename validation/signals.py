from __future__ import annotations

import logging
import time

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from core_settings.models import SettingDefinition, SettingValue
from validation.duplicate_checker import find_potential_duplicate_invoice
from validation.fraud_detector import detect_suspicious_transaction, find_negative_stock
from validation.gst_checker import check_gst_mismatch
from validation.models import FraudAlert

logger = logging.getLogger(__name__)

_enabled_cache = {"ts": 0.0, "value": True}


def _get_global_setting(key: str, default):
    try:
        d = SettingDefinition.objects.filter(key=key).first()
        if not d:
            return default
        v = SettingValue.objects.filter(definition=d, owner__isnull=True).first()
        return v.value if v else d.default_value
    except Exception:
        return default


def smart_alerts_enabled() -> bool:
    now = time.time()
    if now - _enabled_cache["ts"] < 60:
        return bool(_enabled_cache["value"])
    val = bool(_get_global_setting("ai_tools_enabled", True)) and bool(_get_global_setting("smart_alerts_enabled", True))
    _enabled_cache["ts"] = now
    _enabled_cache["value"] = val
    return bool(val)


Invoice = apps.get_model("commerce", "Invoice")
KhataTransaction = apps.get_model("khataapp", "Transaction")


@receiver(post_save, sender=Invoice)
def smart_alerts_invoice(sender, instance, created, **kwargs):
    try:
        if not smart_alerts_enabled():
            return
        owner = getattr(getattr(instance, "order", None), "owner", None)
        if not owner:
            return

        dup = find_potential_duplicate_invoice(instance)
        if dup:
            FraudAlert.objects.update_or_create(
                owner=owner,
                alert_type=FraudAlert.AlertType.DUPLICATE_INVOICE,
                reference_type="commerce.Invoice",
                reference_id=instance.id,
                defaults={
                    "severity": FraudAlert.Severity.MEDIUM,
                    "status": FraudAlert.Status.OPEN,
                    "title": "Potential duplicate invoice",
                    "message": f"Similar invoice detected: {getattr(dup, 'number', '') or 'Invoice'} (id={dup.id}).",
                    "payload": {"duplicate_invoice_id": dup.id},
                },
            )

        gst = check_gst_mismatch(instance)
        if not gst.ok:
            FraudAlert.objects.update_or_create(
                owner=owner,
                alert_type=FraudAlert.AlertType.GST_MISMATCH,
                reference_type="commerce.Invoice",
                reference_id=instance.id,
                defaults={
                    "severity": FraudAlert.Severity.HIGH,
                    "status": FraudAlert.Status.OPEN,
                    "title": "GST configuration mismatch",
                    "message": gst.message,
                    "payload": {},
                },
            )

        # Negative stock check (run after commit so stock ledger posting can complete).
        try:
            order = getattr(instance, "order", None)
            item_product_ids = list(
                order.items.values_list("product_id", flat=True)  # type: ignore[attr-defined]
                if order and hasattr(order, "items")
                else []
            )

            def _check_negative():
                try:
                    negatives = find_negative_stock(owner, product_ids=[pid for pid in item_product_ids if pid])
                    if not negatives:
                        return
                    FraudAlert.objects.update_or_create(
                        owner=owner,
                        alert_type=FraudAlert.AlertType.NEGATIVE_STOCK,
                        reference_type="commerce.Invoice",
                        reference_id=instance.id,
                        defaults={
                            "severity": FraudAlert.Severity.HIGH,
                            "status": FraudAlert.Status.OPEN,
                            "title": "Negative stock detected",
                            "message": "Some products went negative after this invoice.",
                            "payload": {"negatives": negatives},
                        },
                    )
                except Exception:
                    logger.exception("Negative stock check failed for invoice id=%s", getattr(instance, "id", None))

            if item_product_ids:
                transaction.on_commit(_check_negative)
        except Exception:
            pass
    except Exception:
        logger.exception("Smart alerts failed for invoice id=%s", getattr(instance, "id", None))


@receiver(post_save, sender=KhataTransaction)
def smart_alerts_txn(sender, instance, created, **kwargs):
    try:
        if not smart_alerts_enabled():
            return
        party = getattr(instance, "party", None)
        owner = getattr(party, "owner", None) if party else None
        if not owner:
            return

        sus = detect_suspicious_transaction(instance)
        if not sus.ok:
            FraudAlert.objects.update_or_create(
                owner=owner,
                alert_type=FraudAlert.AlertType.SUSPICIOUS_TXN,
                reference_type="khataapp.Transaction",
                reference_id=instance.id,
                defaults={
                    "severity": FraudAlert.Severity.MEDIUM,
                    "status": FraudAlert.Status.OPEN,
                    "title": "Suspicious transaction",
                    "message": sus.message,
                    "payload": {"score": sus.score},
                },
            )
    except Exception:
        logger.exception("Smart alerts failed for transaction id=%s", getattr(instance, "id", None))
