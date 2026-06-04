from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.platform.core.application.services.event_service import EventService
from apps.platform.tax_compliance.infrastructure.repositories.tax_repository import TaxRepository
from apps.platform.tax_compliance.models import GSTInvoice
from apps.platform.tax_compliance.application.services.validators import IndianTaxValidator


TWOPLACES = Decimal("0.01")
EWAY_THRESHOLD = Decimal("50000.00")


def money(value):
    return Decimal(value or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class GSTService:
    def __init__(self, repository=None, validator=None, event_service=None):
        self.repository = repository or TaxRepository()
        self.validator = validator or IndianTaxValidator()
        self.event_service = event_service or EventService()

    @transaction.atomic
    def calculate_invoice(self, invoice):
        totals = {
            "subtotal": Decimal("0.00"),
            "taxable_value": Decimal("0.00"),
            "cgst_amount": Decimal("0.00"),
            "sgst_amount": Decimal("0.00"),
            "igst_amount": Decimal("0.00"),
            "cess_amount": Decimal("0.00"),
            "total_amount": Decimal("0.00"),
        }
        interstate = invoice.seller_state_code != invoice.place_of_supply_state_code
        for line in invoice.lines.select_related("hsn_sac", "hsn_sac__tax_slab"):
            slab = line.hsn_sac.tax_slab
            rate = Decimal(str(line.tax_rate or (slab.rate if slab else 0)))
            cess_rate = Decimal(str(slab.cess_rate if slab else 0))
            taxable = money((line.quantity * line.unit_price) - line.discount)
            tax = money(taxable * rate / Decimal("100"))
            cess = money(taxable * cess_rate / Decimal("100"))
            if interstate:
                cgst = Decimal("0.00")
                sgst = Decimal("0.00")
                igst = tax
            else:
                cgst = money(tax / 2)
                sgst = money(tax / 2)
                igst = Decimal("0.00")
            line.taxable_value = taxable
            line.tax_rate = rate
            line.cgst_amount = cgst
            line.sgst_amount = sgst
            line.igst_amount = igst
            line.cess_amount = cess
            line.total = money(taxable + cgst + sgst + igst + cess)
            line.save(update_fields=["taxable_value", "tax_rate", "cgst_amount", "sgst_amount", "igst_amount", "cess_amount", "total"])
            totals["subtotal"] += taxable
            totals["taxable_value"] += taxable
            totals["cgst_amount"] += cgst
            totals["sgst_amount"] += sgst
            totals["igst_amount"] += igst
            totals["cess_amount"] += cess
            totals["total_amount"] += line.total
        totals = {key: money(value) for key, value in totals.items()}
        self.repository.save_invoice_totals(invoice, totals)
        return invoice

    @transaction.atomic
    def validate_invoice(self, invoice, user=None):
        self.calculate_invoice(invoice)
        issues = self.validator.invoice_issues(invoice)
        self.repository.replace_validation_issues(invoice, issues)
        has_error = any(issue["severity"] == "error" for issue in issues)
        if has_error:
            invoice.status = GSTInvoice.Status.DRAFT
        elif invoice.total_amount > EWAY_THRESHOLD:
            invoice.status = GSTInvoice.Status.EWAY_REQUIRED
            self.repository.eway_for_invoice(invoice)
        else:
            invoice.status = GSTInvoice.Status.VALIDATED
        invoice.save(update_fields=["status", "updated_at"])
        self.repository.audit(tenant=invoice.tenant, invoice=invoice, actor=user, action="gst_invoice_validated", after={"status": invoice.status})
        self.event_service.publish("gst_invoice_validated", {"invoice_id": str(invoice.id), "status": invoice.status}, tenant=invoice.tenant, user=user)
        return {"invoice": invoice, "issues": issues, "eway_required": invoice.total_amount > EWAY_THRESHOLD}

    def issue_invoice(self, invoice, user=None):
        validation = self.validate_invoice(invoice, user=user)
        if validation["issues"]:
            errors = [issue for issue in validation["issues"] if issue["severity"] == "error"]
            if errors:
                return validation
        if invoice.status != GSTInvoice.Status.EWAY_REQUIRED:
            invoice.status = GSTInvoice.Status.ISSUED
            invoice.save(update_fields=["status", "updated_at"])
            self.event_service.publish("gst_invoice_issued", {"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number}, tenant=invoice.tenant, user=user)
        return validation

