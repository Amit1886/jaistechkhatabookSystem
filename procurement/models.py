from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SupplierProduct(models.Model):
    """
    Explicit mapping between a Product and multiple Suppliers (Parties).

    Note: Supplier master data is stored in `khataapp.Party` with `party_type='supplier'`.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )
    product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.CASCADE,
        related_name="supplier_products",
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    moq = models.PositiveIntegerField(default=1, verbose_name="Minimum order qty")
    delivery_days = models.PositiveIntegerField(default=1)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "supplier", "product")
        indexes = [
            models.Index(fields=["owner", "product"]),
            models.Index(fields=["owner", "supplier"]),
            models.Index(fields=["owner", "product", "supplier"]),
        ]
        ordering = ["product_id", "supplier_id"]
        verbose_name = "Supplier Product"
        verbose_name_plural = "Supplier Products"

    def __str__(self) -> str:
        return f"{self.supplier_id} -> {self.product_id} @ {self.price}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        old_price = None
        if not creating:
            old_price = (
                SupplierProduct.objects.filter(pk=self.pk)
                .values_list("price", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if creating:
            return

        if old_price is None:
            return

        try:
            old_price_dec = Decimal(str(old_price))
            new_price_dec = Decimal(str(self.price))
        except Exception:
            return

        if old_price_dec == new_price_dec:
            return

        change_pct = Decimal("0.00")
        if old_price_dec and old_price_dec != Decimal("0.00"):
            try:
                change_pct = ((new_price_dec - old_price_dec) / old_price_dec) * Decimal("100")
            except Exception:
                change_pct = Decimal("0.00")

        updated_by = getattr(self, "_updated_by", None)
        SupplierPriceHistory.objects.create(
            owner=self.owner,
            supplier=self.supplier,
            product=self.product,
            old_price=old_price_dec,
            new_price=new_price_dec,
            change_pct=change_pct.quantize(Decimal("0.01")),
            updated_by=updated_by if getattr(updated_by, "pk", None) else None,
        )

        try:
            threshold = Decimal(str(getattr(self, "_alert_threshold_pct", "10.00") or "10.00"))
        except Exception:
            threshold = Decimal("10.00")

        if abs(change_pct) >= abs(threshold):
            SupplierPriceAlert.objects.create(
                owner=self.owner,
                supplier=self.supplier,
                product=self.product,
                old_price=old_price_dec,
                new_price=new_price_dec,
                change_pct=change_pct.quantize(Decimal("0.01")),
                direction=SupplierPriceAlert.Direction.UP if new_price_dec > old_price_dec else SupplierPriceAlert.Direction.DOWN,
                threshold_pct=abs(threshold),
            )


class SupplierPriceHistory(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_price_history",
    )
    supplier = models.ForeignKey("khataapp.Party", on_delete=models.CASCADE, related_name="price_history")
    product = models.ForeignKey("commerce.Product", on_delete=models.CASCADE, related_name="supplier_price_history")
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    change_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_price_updates",
    )
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "product", "supplier"]),
            models.Index(fields=["owner", "supplier", "updated_at"]),
        ]
        ordering = ["-updated_at", "-id"]
        verbose_name = "Supplier Price History"
        verbose_name_plural = "Supplier Price History"

    def __str__(self) -> str:
        return f"{self.supplier_id} {self.product_id}: {self.old_price} -> {self.new_price}"


class SupplierRating(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_ratings",
    )
    supplier = models.ForeignKey("khataapp.Party", on_delete=models.CASCADE, related_name="ratings")
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_supplier_ratings",
    )
    delivery_speed = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    product_quality = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    pricing = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "supplier", "rated_by")
        indexes = [
            models.Index(fields=["owner", "supplier"]),
            models.Index(fields=["owner", "rated_by"]),
        ]
        ordering = ["-updated_at", "-id"]
        verbose_name = "Supplier Rating"
        verbose_name_plural = "Supplier Ratings"

    @property
    def average(self) -> Decimal:
        try:
            return (Decimal(self.delivery_speed) + Decimal(self.product_quality) + Decimal(self.pricing)) / Decimal("3")
        except Exception:
            return Decimal("0.00")

    def __str__(self) -> str:
        return f"{self.supplier_id} rated by {self.rated_by_id}: {self.average}"


class SupplierPriceAlert(models.Model):
    class Direction(models.TextChoices):
        UP = "up", "Increase"
        DOWN = "down", "Decrease"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_price_alerts",
    )
    supplier = models.ForeignKey("khataapp.Party", on_delete=models.CASCADE, related_name="price_alerts")
    product = models.ForeignKey("commerce.Product", on_delete=models.CASCADE, related_name="supplier_price_alerts")
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    change_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    direction = models.CharField(max_length=8, choices=Direction.choices, default=Direction.UP)
    threshold_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "is_read", "created_at"]),
            models.Index(fields=["owner", "product", "created_at"]),
        ]
        ordering = ["is_read", "-created_at", "-id"]
        verbose_name = "Supplier Price Alert"
        verbose_name_plural = "Supplier Price Alerts"

    def __str__(self) -> str:
        return f"Alert {self.product_id} {self.direction} {self.change_pct}%"


class InvoiceSource(models.Model):
    """
    Centralized capture record for supplier invoice inputs (OCR/WhatsApp/Email/etc).
    """

    class SourceType(models.TextChoices):
        OCR_SCAN = "ocr_scan", "OCR Scan"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        PORTAL = "portal", "Supplier Portal"
        VOICE = "voice", "Voice"
        EXCEL = "excel", "Excel"
        PDF = "pdf", "PDF"
        API = "api", "Supplier ERP/API"
        MANUAL = "manual", "Manual Upload"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        EXTRACTED = "extracted", "Extracted"
        DRAFTED = "drafted", "Draft Created"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_sources",
        db_index=True,
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices, db_index=True)
    external_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    file = models.FileField(upload_to="invoice_sources/", blank=True, null=True)
    content_type = models.CharField(max_length=120, blank=True, default="")
    extracted_text = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    error = models.TextField(blank=True, default="")

    # Linkage to downstream objects (kept generic to avoid tight coupling).
    reference_type = models.CharField(max_length=100, blank=True, default="", db_index=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_sources"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="invsrc_owner_dt_idx"),
            models.Index(fields=["owner", "source_type", "created_at"], name="invsrc_owner_tp_dt_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="invsrc_owner_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"InvoiceSource #{self.id} ({self.source_type}/{self.status})"


class SupplierTemplate(models.Model):
    """
    Stores learned invoice parsing hints per supplier (template learning).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_templates",
        db_index=True,
    )
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="invoice_templates",
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    template = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_used_at = models.DateTimeField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_templates"
        ordering = ["supplier_id", "-is_active", "-updated_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "supplier", "is_active"], name="suptpl_owner_sup_idx"),
            models.Index(fields=["owner", "is_active", "updated_at"], name="suptpl_owner_act_idx"),
        ]

    def __str__(self) -> str:
        return f"SupplierTemplate {self.supplier_id} v{self.version} (active={self.is_active})"


class ProductUnit(models.Model):
    """
    Unit normalization rules per product.

    Example:
      product.unit = "kg" (base)
      ProductUnit(unit_name="bag", multiplier=50)  => 1 bag = 50 kg
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_units",
        db_index=True,
    )
    product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.CASCADE,
        related_name="unit_conversions",
        db_index=True,
    )
    unit_name = models.CharField(max_length=50, db_index=True)
    multiplier = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("1.000000"))
    synonyms = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_units"
        ordering = ["product_id", "unit_name", "-is_active", "-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "product", "unit_name"], name="uniq_owner_product_unit"),
        ]
        indexes = [
            models.Index(fields=["owner", "product"], name="prunit_owner_prod_idx"),
            models.Index(fields=["owner", "unit_name"], name="prunit_owner_unit_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} {self.unit_name} x{self.multiplier}"


class SupplierProductAlias(models.Model):
    """
    Self-learning mapping from supplier invoice raw names to internal products.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_product_aliases",
        db_index=True,
    )
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="product_aliases",
        db_index=True,
    )
    raw_name = models.CharField(max_length=200, db_index=True)
    normalized_name = models.CharField(max_length=220, db_index=True, blank=True, default="")
    product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.CASCADE,
        related_name="supplier_aliases",
        db_index=True,
    )
    confidence = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("1.000"))
    times_used = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_product_aliases"
        ordering = ["supplier_id", "normalized_name", "-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "supplier", "normalized_name"], name="uniq_owner_supplier_alias"),
        ]
        indexes = [
            models.Index(fields=["owner", "supplier"], name="spalias_owner_sup_idx"),
            models.Index(fields=["owner", "normalized_name"], name="spalias_owner_nm_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.normalized_name:
            self.normalized_name = (self.raw_name or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.supplier_id}: {self.raw_name} -> {self.product_id}"


class PurchaseDraft(models.Model):
    """
    Standardized purchase draft object used by the robotic purchase pipeline.
    """

    class Status(models.TextChoices):
        CAPTURED = "captured", "Captured"
        EXTRACTED = "extracted", "Extracted"
        MATCHED = "matched", "Matched"
        VALIDATED = "validated", "Validated"
        READY = "ready", "Ready"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        POSTED = "posted", "Posted"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchase_drafts",
        db_index=True,
    )
    source = models.ForeignKey(
        InvoiceSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_drafts",
    )

    supplier_name = models.CharField(max_length=200, blank=True, default="")
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_drafts",
        db_index=True,
    )
    invoice_number = models.CharField(max_length=80, blank=True, default="", db_index=True)
    invoice_date = models.DateField(blank=True, null=True, db_index=True)

    currency = models.CharField(max_length=10, blank=True, default="INR")
    subtotal_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), db_index=True)
    gst_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    confidence = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"), db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CAPTURED, db_index=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True, default="")

    auto_approved = models.BooleanField(default=False, db_index=True)
    created_order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="automation_purchase_drafts",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "purchase_drafts"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "created_at"], name="pdraft_owner_st_dt_idx"),
            models.Index(fields=["owner", "supplier", "created_at"], name="pdraft_owner_sup_dt_idx"),
            models.Index(fields=["owner", "invoice_number"], name="pdraft_owner_invno_idx"),
        ]

    def __str__(self) -> str:
        return f"PurchaseDraft #{self.id} ({self.status})"

    def recompute_totals(self, *, save: bool = True) -> None:
        subtotal = Decimal("0.00")
        tax = Decimal("0.00")
        total = Decimal("0.00")
        for it in self.items.all():
            try:
                line = (it.amount or Decimal("0.00"))
            except Exception:
                line = Decimal("0.00")
            subtotal += line
        # Tax amount is optional (many drafts store inclusive totals only).
        if self.tax_amount and self.tax_amount > 0:
            tax = self.tax_amount
        total = subtotal + tax
        self.subtotal_amount = subtotal.quantize(Decimal("0.01"))
        self.total_amount = total.quantize(Decimal("0.01"))
        if save:
            self.save(update_fields=["subtotal_amount", "total_amount", "updated_at"])


class PurchaseDraftItem(models.Model):
    draft = models.ForeignKey(PurchaseDraft, on_delete=models.CASCADE, related_name="items", db_index=True)
    line_no = models.PositiveIntegerField(default=1)

    raw_name = models.CharField(max_length=200, blank=True, default="")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    unit = models.CharField(max_length=30, blank=True, default="")
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gst_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    normalized_quantity = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0.000000"))
    normalized_unit = models.CharField(max_length=30, blank=True, default="")

    matched_product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_draft_items",
        db_index=True,
    )
    match_confidence = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"), db_index=True)
    match_method = models.CharField(max_length=30, blank=True, default="")
    requires_review = models.BooleanField(default=False, db_index=True)
    notes = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        db_table = "purchase_draft_items"
        ordering = ["draft_id", "line_no", "id"]
        indexes = [
            models.Index(fields=["draft", "requires_review"], name="pdi_draft_review_idx"),
            models.Index(fields=["draft", "matched_product"], name="pdi_draft_prod_idx"),
        ]

    def __str__(self) -> str:
        return f"DraftItem #{self.id} ({self.raw_name})"


class PurchaseInvoice(models.Model):
    """
    Optional automation-layer purchase invoice table.

    This does NOT replace existing billing/commerce workflows.
    It tracks invoices processed by the AR-CSSPS engine and links to the created
    commerce.Order/Invoice records.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        DUPLICATE = "duplicate", "Duplicate"
        POSTED = "posted", "Posted"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchase_invoices",
        db_index=True,
    )
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="purchase_invoices",
        db_index=True,
    )
    invoice_number = models.CharField(max_length=80, blank=True, default="", db_index=True)
    invoice_date = models.DateField(blank=True, null=True, db_index=True)
    invoice_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), db_index=True)
    source = models.ForeignKey(
        InvoiceSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_invoices",
    )
    draft = models.ForeignKey(
        PurchaseDraft,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_invoices",
    )
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_invoice_records",
        db_index=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "purchase_invoices"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "supplier", "invoice_number"], name="purchinv_owner_sup_no_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="purchinv_owner_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"PurchaseInvoice #{self.id} {self.invoice_number}"


class PurchaseItem(models.Model):
    purchase_invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="items", db_index=True)
    product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_items",
        db_index=True,
    )
    raw_name = models.CharField(max_length=200, blank=True, default="")
    qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    unit = models.CharField(max_length=30, blank=True, default="")
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gst_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "purchase_items"
        ordering = ["purchase_invoice_id", "id"]
        indexes = [
            models.Index(fields=["purchase_invoice", "product"], name="purchit_inv_prod_idx"),
        ]

    def __str__(self) -> str:
        return f"PurchaseItem #{self.id}"


class AITrainingLog(models.Model):
    """
    Self-learning log of user corrections and automation decisions.
    """

    class EventType(models.TextChoices):
        PRODUCT_MATCH = "product_match", "Product Match"
        PRODUCT_MATCH_CORRECTION = "product_match_correction", "Product Match Correction"
        UNIT_CONVERSION_EDIT = "unit_conversion_edit", "Unit Conversion Edit"
        SUPPLIER_TEMPLATE_UPDATE = "supplier_template_update", "Supplier Template Update"
        DRAFT_APPROVED = "draft_approved", "Draft Approved"
        DRAFT_REJECTED = "draft_rejected", "Draft Rejected"
        AUTO_APPROVED = "auto_approved", "Auto Approved"
        VALIDATION_WARNING = "validation_warning", "Validation Warning"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_training_logs",
        db_index=True,
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    reference_type = models.CharField(max_length=100, blank=True, default="", db_index=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ai_training_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "event_type", "created_at"], name="ailog_owner_tp_dt_idx"),
            models.Index(fields=["reference_type", "reference_id"], name="ailog_ref_idx"),
        ]

    def __str__(self) -> str:
        return f"AITrainingLog #{self.id} ({self.event_type})"


class SupplierAPIConnection(models.Model):
    """
    Prepared infrastructure for future Supplier ERP/API integration.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_api_connections",
        db_index=True,
    )
    supplier = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="api_connections",
        db_index=True,
    )
    name = models.CharField(max_length=120, blank=True, default="")
    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_api_connections"
        ordering = ["supplier_id", "-updated_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "supplier"], name="sapiconn_owner_sup_idx"),
            models.Index(fields=["owner", "status"], name="sapiconn_owner_st_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"SupplierAPIConnection #{self.id} ({self.status})"
