from urllib.parse import quote


class PaymentQRService:
    def upi_uri(self, invoice):
        profile = invoice.payment_profile
        if not profile or not profile.upi_id:
            return ""
        return (
            "upi://pay"
            f"?pa={quote(profile.upi_id)}"
            f"&pn={quote(profile.account_name or profile.name)}"
            f"&am={quote(str(invoice.total_amount))}"
            "&cu=INR"
            f"&tn={quote(invoice.invoice_number)}"
        )

    def invoice_payment_block(self, invoice):
        profile = invoice.payment_profile
        if not profile:
            return {}
        return {
            "upi_id": profile.upi_id,
            "upi_uri": self.upi_uri(invoice),
            "bank_name": profile.bank_name,
            "account_name": profile.account_name,
            "account_number": profile.account_number,
            "ifsc": profile.ifsc,
            "payment_link": profile.payment_link,
        }

