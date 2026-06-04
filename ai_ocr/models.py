from __future__ import annotations

from django.conf import settings
from django.db import models


class OCRInvoiceLog(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        OCR_OK = "ocr_ok", "OCR OK"
        PARSED = "parsed", "Parsed"
        CREATED = "created", "Purchase Created"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ocr_invoice_logs",
        db_index=True,
    )
    image = models.ImageField(upload_to="ocr_invoices/", blank=True, null=True)

    extracted_text = models.TextField(blank=True, default="")
    parsed_data = models.JSONField(default=dict, blank=True)

    reference_type = models.CharField(max_length=100, blank=True, default="", db_index=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ocr_invoice_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="ocr_owner_dt_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="ocr_owner_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"OCR Invoice #{self.id} ({self.status})"

