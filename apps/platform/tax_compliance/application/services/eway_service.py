from django.db import transaction
from django.utils import timezone

from apps.platform.tax_compliance.application.services.validators import IndianTaxValidator
from apps.platform.tax_compliance.infrastructure.repositories.tax_repository import TaxRepository
from apps.platform.tax_compliance.models import EWayBillRequest, GSTInvoice


class EWayBillService:
    def __init__(self, repository=None, validator=None):
        self.repository = repository or TaxRepository()
        self.validator = validator or IndianTaxValidator()

    def required_fields_prompt(self):
        return [
            "transporter_name",
            "transporter_gstin",
            "vehicle_number",
            "transport_mode",
            "distance_km",
            "dispatch_address",
            "dispatch_pincode",
            "delivery_address",
            "delivery_pincode",
        ]

    @transaction.atomic
    def prepare(self, invoice, **transport_data):
        eway = self.repository.eway_for_invoice(invoice)
        for field in self.required_fields_prompt():
            if field in transport_data:
                setattr(eway, field, transport_data[field])
        eway.status = EWayBillRequest.Status.DRAFT
        eway.save()
        issues = self.validator.eway_issues(eway)
        if not issues:
            eway.eway_ready_payload = self.ready_payload(eway)
            eway.status = EWayBillRequest.Status.READY
            eway.save(update_fields=["eway_ready_payload", "status", "updated_at"])
            invoice.status = GSTInvoice.Status.EWAY_READY
            invoice.save(update_fields=["status", "updated_at"])
        return {"eway": eway, "issues": issues}

    def ready_payload(self, eway):
        invoice = eway.invoice
        first_line = invoice.lines.select_related("hsn_sac").first()
        return {
            "supplyType": invoice.supply_type,
            "subSupplyType": eway.reason_for_transport,
            "docType": "INV",
            "docNo": invoice.invoice_number,
            "docDate": invoice.invoice_date.isoformat(),
            "fromGstin": invoice.seller_gstin,
            "toGstin": invoice.buyer.gstin,
            "toPincode": invoice.buyer.pincode or eway.delivery_pincode,
            "placeOfDelivery": eway.delivery_pincode,
            "transactionType": "regular",
            "totalValue": str(invoice.taxable_value),
            "cgstValue": str(invoice.cgst_amount),
            "sgstValue": str(invoice.sgst_amount),
            "igstValue": str(invoice.igst_amount),
            "cessValue": str(invoice.cess_amount),
            "totInvValue": str(invoice.total_amount),
            "mainHsnCode": first_line.hsn_sac.code if first_line else "",
            "transporterName": eway.transporter_name,
            "transporterId": eway.transporter_gstin,
            "transDocNo": eway.transporter_doc_no,
            "transMode": eway.transport_mode,
            "transDistance": eway.distance_km,
            "vehicleNo": eway.vehicle_number,
            "dispatchFrom": {
                "address": eway.dispatch_address,
                "pincode": eway.dispatch_pincode,
            },
            "shipTo": {
                "address": eway.delivery_address,
                "pincode": eway.delivery_pincode,
            },
        }

    def mark_generated(self, eway, eway_bill_no):
        eway.eway_bill_no = eway_bill_no
        eway.status = EWayBillRequest.Status.GENERATED
        eway.generated_at = timezone.now()
        eway.save(update_fields=["eway_bill_no", "status", "generated_at", "updated_at"])
        return eway

