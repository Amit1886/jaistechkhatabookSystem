import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.platform.identity.models import Tenant


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_records")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class GSTTaxSlab(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "tax_gst_slabs"
        unique_together = ("rate", "cess_rate")
        ordering = ("rate",)

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class HSNSACCode(TimestampedModel):
    class CodeType(models.TextChoices):
        HSN = "hsn", "HSN"
        SAC = "sac", "SAC"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=12, db_index=True)
    code_type = models.CharField(max_length=8, choices=CodeType.choices, db_index=True)
    description = models.CharField(max_length=260)
    tax_slab = models.ForeignKey(GSTTaxSlab, on_delete=models.SET_NULL, null=True, blank=True, related_name="hsn_sac_codes")
    is_goods = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "tax_hsn_sac_codes"
        unique_together = ("code", "code_type")
        ordering = ("code",)

    def __str__(self):
        return self.code


class GSTParty(TenantScopedModel):
    class PartyType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        SUPPLIER = "supplier", "Supplier"
        TRANSPORTER = "transporter", "Transporter"

    party_type = models.CharField(max_length=20, choices=PartyType.choices, db_index=True)
    name = models.CharField(max_length=180)
    gstin = models.CharField(max_length=15, blank=True, default="", db_index=True)
    pan = models.CharField(max_length=10, blank=True, default="", db_index=True)
    state_code = models.CharField(max_length=2, db_index=True)
    address = models.TextField(blank=True, default="")
    pincode = models.CharField(max_length=8, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        db_table = "tax_gst_parties"
        indexes = [models.Index(fields=["tenant", "party_type", "gstin"])]

    def __str__(self):
        return self.name


class PaymentQRProfile(TenantScopedModel):
    name = models.CharField(max_length=160)
    upi_id = models.CharField(max_length=120, blank=True, default="")
    bank_name = models.CharField(max_length=160, blank=True, default="")
    account_name = models.CharField(max_length=180, blank=True, default="")
    account_number = models.CharField(max_length=60, blank=True, default="")
    ifsc = models.CharField(max_length=16, blank=True, default="")
    payment_link = models.CharField(max_length=500, blank=True, default="")
    is_default = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "tax_payment_qr_profiles"
        indexes = [models.Index(fields=["tenant", "is_default"])]

    def __str__(self):
        return self.name


class GSTInvoice(TenantScopedModel):
    class InvoiceType(models.TextChoices):
        TAX_INVOICE = "tax_invoice", "Tax Invoice"
        BILL_OF_SUPPLY = "bill_of_supply", "Bill of Supply"
        CREDIT_NOTE = "credit_note", "Credit Note"
        DEBIT_NOTE = "debit_note", "Debit Note"

    class SupplyType(models.TextChoices):
        B2B = "b2b", "B2B"
        B2C = "b2c", "B2C"
        EXPORT = "export", "Export"
        SEZ = "sez", "SEZ"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        EWAY_REQUIRED = "eway_required", "E-Way Required"
        EWAY_READY = "eway_ready", "E-Way Ready"
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"

    invoice_number = models.CharField(max_length=80, db_index=True)
    invoice_date = models.DateField(default=timezone.localdate, db_index=True)
    invoice_type = models.CharField(max_length=30, choices=InvoiceType.choices, default=InvoiceType.TAX_INVOICE)
    supply_type = models.CharField(max_length=20, choices=SupplyType.choices, default=SupplyType.B2B, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    seller_gstin = models.CharField(max_length=15, db_index=True)
    seller_state_code = models.CharField(max_length=2, db_index=True)
    buyer = models.ForeignKey(GSTParty, on_delete=models.PROTECT, related_name="gst_invoices")
    place_of_supply_state_code = models.CharField(max_length=2, db_index=True)
    reverse_charge = models.BooleanField(default=False, db_index=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    round_off = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    source_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    payment_profile = models.ForeignKey(PaymentQRProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")

    class Meta:
        db_table = "tax_gst_invoices"
        unique_together = ("tenant", "invoice_number")
        ordering = ("-invoice_date", "-created_at")

    @property
    def eway_required(self):
        return self.total_amount > Decimal("50000.00")


class GSTInvoiceLine(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(GSTInvoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=260)
    hsn_sac = models.ForeignKey(HSNSACCode, on_delete=models.PROTECT, related_name="invoice_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="pcs")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "tax_gst_invoice_lines"


class EWayBillRequest(TenantScopedModel):
    class Status(models.TextChoices):
        REQUIRED = "required", "Required"
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        GENERATED = "generated", "Generated"
        CANCELLED = "cancelled", "Cancelled"

    class TransportMode(models.TextChoices):
        ROAD = "road", "Road"
        RAIL = "rail", "Rail"
        AIR = "air", "Air"
        SHIP = "ship", "Ship"

    invoice = models.OneToOneField(GSTInvoice, on_delete=models.CASCADE, related_name="eway_bill")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUIRED, db_index=True)
    transporter_name = models.CharField(max_length=180, blank=True, default="")
    transporter_gstin = models.CharField(max_length=15, blank=True, default="")
    transporter_doc_no = models.CharField(max_length=80, blank=True, default="")
    transporter_doc_date = models.DateField(null=True, blank=True)
    vehicle_number = models.CharField(max_length=30, blank=True, default="")
    transport_mode = models.CharField(max_length=20, choices=TransportMode.choices, default=TransportMode.ROAD)
    distance_km = models.PositiveIntegerField(default=0)
    dispatch_address = models.TextField(blank=True, default="")
    dispatch_pincode = models.CharField(max_length=8, blank=True, default="")
    delivery_address = models.TextField(blank=True, default="")
    delivery_pincode = models.CharField(max_length=8, blank=True, default="")
    reason_for_transport = models.CharField(max_length=40, default="supply")
    eway_ready_payload = models.JSONField(default=dict, blank=True)
    eway_bill_no = models.CharField(max_length=80, blank=True, default="", db_index=True)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tax_eway_bill_requests"
        ordering = ("-created_at",)


class TaxValidationIssue(TenantScopedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    invoice = models.ForeignKey(GSTInvoice, on_delete=models.CASCADE, null=True, blank=True, related_name="validation_issues")
    code = models.CharField(max_length=80, db_index=True)
    message = models.CharField(max_length=260)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.ERROR, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tax_validation_issues"
        indexes = [models.Index(fields=["tenant", "severity", "code"])]


class TaxAuditLog(TenantScopedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tax_audit_logs")
    invoice = models.ForeignKey(GSTInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=120, db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "tax_audit_logs"
        ordering = ("-created_at",)


class GSTReportSnapshot(TenantScopedModel):
    class ReportType(models.TextChoices):
        SALES_REGISTER = "sales_register", "GST Sales Register"
        PURCHASE_REGISTER = "purchase_register", "GST Purchase Register"
        TAX_SUMMARY = "tax_summary", "Tax Summary"
        HSN_SUMMARY = "hsn_summary", "HSN Summary"
        GSTR1 = "gstr1", "GSTR-1"
        GSTR3B = "gstr3b", "GSTR-3B"
        EWAY = "eway", "E-Way Bill Report"
        TRANSPORTER = "transporter", "Transporter Report"

    report_type = models.CharField(max_length=40, choices=ReportType.choices, db_index=True)
    period = models.CharField(max_length=20, db_index=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="gst_report_snapshots")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "tax_gst_report_snapshots"
        unique_together = ("tenant", "report_type", "period")

