from __future__ import annotations

from celery import shared_task


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def generate_invoice_pdf_task(self, invoice_id: int) -> dict:
    """
    Blueprint task: generate invoice PDF asynchronously.
    Hook this into billing module's invoice creation flow.
    """
    # TODO: import billing invoice generator and store to S3/local storage
    return {"ok": True, "invoice_id": int(invoice_id), "status": "queued_placeholder"}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def whatsapp_notify_task(self, vendor_id: int, template_key: str, payload: dict) -> dict:
    """
    Blueprint task: send WhatsApp notifications (order placed/accepted/shipped).
    """
    return {"ok": True, "vendor_id": int(vendor_id), "template": template_key, "status": "queued_placeholder"}

