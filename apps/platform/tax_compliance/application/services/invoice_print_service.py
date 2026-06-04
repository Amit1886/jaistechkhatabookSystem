from apps.platform.tax_compliance.application.services.payment_qr_service import PaymentQRService


class InvoicePrintService:
    def render_context(self, invoice, copy_type="customer", layout="a4"):
        return {
            "layout": layout,
            "copy_type": copy_type,
            "invoice": invoice,
            "lines": list(invoice.lines.select_related("hsn_sac")),
            "buyer": invoice.buyer,
            "eway": getattr(invoice, "eway_bill", None),
            "payment": PaymentQRService().invoice_payment_block(invoice),
            "supported_layouts": ["a4", "thermal", "transporter_copy", "customer_copy"],
        }

