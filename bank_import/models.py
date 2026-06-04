from __future__ import annotations

from django.conf import settings
from django.db import models


class BankImportLog(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PREVIEWED = "previewed", "Previewed"
        IMPORTED = "imported", "Imported"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_import_logs",
        db_index=True,
    )
    file = models.FileField(upload_to="bank_statements/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "bank_import_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="bankimp_owner_dt_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="bankimp_owner_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"BankImport #{self.id} ({self.status})"

