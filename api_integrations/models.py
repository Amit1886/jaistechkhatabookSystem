from __future__ import annotations

from django.conf import settings
from django.db import models


class IntegrationProvider(models.TextChoices):
    WHATSAPP_GATEWAY = "whatsapp_gateway", "WhatsApp Gateway"
    WHATSAPP_META = "whatsapp_meta", "WhatsApp Cloud API (Meta)"
    SMS = "sms", "SMS Gateway"
    EMAIL_SMTP = "email_smtp", "Email SMTP"
    RAZORPAY = "razorpay", "Razorpay"
    STRIPE = "stripe", "Stripe"
    BANK_PAYOUT = "bank_payout", "Bank Payout API"


class IntegrationConnection(models.Model):
    """
    Per-tenant external integration configuration.

    NOTE: Credentials are stored in JSON for now; in production you should store secrets
    in a managed secrets store and keep only reference IDs here.
    """

    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integration_connections",
    )
    provider = models.CharField(max_length=40, choices=IntegrationProvider.choices, db_index=True)
    name = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    credentials = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_connections_created",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider", "name", "-created_at"]
        indexes = [models.Index(fields=["company", "provider", "is_active"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.name or self.id}"
