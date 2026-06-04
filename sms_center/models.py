from django.db import models


class SMSProviderSettings(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"

    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.GOOGLE, unique=True)
    api_key = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "SMS Provider Setting"
        verbose_name_plural = "SMS Provider Settings"

    def __str__(self) -> str:
        return f"{self.get_provider_display()} (active={self.is_active})"


class SMSTemplate(models.Model):
    class TemplateType(models.TextChoices):
        ORDER = "order", "Order"
        INVOICE = "invoice", "Invoice"
        VOUCHER = "voucher", "Voucher"
        BILLING = "billing", "Billing"

    title = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices, db_index=True)
    message_text = models.TextField(
        help_text="Supports variables: {{name}}, {{amount}}, {{invoice_no}}, {{date}}"
    )
    image_url = models.URLField(blank=True, null=True)
    enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["template_type", "title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.template_type})"


class SMSLog(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    mobile = models.CharField(max_length=30, db_index=True)
    message = models.TextField()
    template = models.ForeignKey(SMSTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT, db_index=True)
    response = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.mobile} [{self.status}] {self.timestamp:%Y-%m-%d %H:%M}"

