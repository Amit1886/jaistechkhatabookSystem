import re


GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
VEHICLE_RE = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")


class IndianTaxValidator:
    def validate_gstin(self, gstin):
        if not gstin:
            return False
        return bool(GSTIN_RE.match(gstin.strip().upper()))

    def validate_pan(self, pan):
        if not pan:
            return False
        return bool(PAN_RE.match(pan.strip().upper()))

    def validate_vehicle_number(self, vehicle_number):
        if not vehicle_number:
            return False
        compact = re.sub(r"[^A-Za-z0-9]", "", vehicle_number).upper()
        return bool(VEHICLE_RE.match(compact))

    def invoice_issues(self, invoice):
        issues = []
        if not self.validate_gstin(invoice.seller_gstin):
            issues.append({"code": "seller_gstin_invalid", "message": "Seller GSTIN is invalid.", "severity": "error"})
        if invoice.supply_type == "b2b" and not self.validate_gstin(invoice.buyer.gstin):
            issues.append({"code": "buyer_gstin_invalid", "message": "Buyer GSTIN is required and invalid for B2B invoice.", "severity": "error"})
        if invoice.buyer.pan and not self.validate_pan(invoice.buyer.pan):
            issues.append({"code": "buyer_pan_invalid", "message": "Buyer PAN format is invalid.", "severity": "warning"})
        if not invoice.lines.exists():
            issues.append({"code": "invoice_lines_missing", "message": "Invoice must contain at least one line.", "severity": "error"})
        for line in invoice.lines.select_related("hsn_sac"):
            if not line.hsn_sac_id:
                issues.append({"code": "hsn_missing", "message": f"HSN/SAC missing for {line.description}.", "severity": "error"})
            elif line.hsn_sac.code_type == "hsn" and len(line.hsn_sac.code) < 2:
                issues.append({"code": "hsn_too_short", "message": f"HSN code {line.hsn_sac.code} is too short.", "severity": "error"})
        return issues

    def eway_issues(self, eway):
        issues = []
        required = {
            "transporter_name": "Transporter name is required.",
            "vehicle_number": "Vehicle number is required.",
            "distance_km": "Distance is required.",
            "dispatch_address": "Dispatch address is required.",
            "delivery_address": "Delivery address is required.",
            "dispatch_pincode": "Dispatch pincode is required.",
            "delivery_pincode": "Delivery pincode is required.",
        }
        for field, message in required.items():
            if not getattr(eway, field):
                issues.append({"code": f"eway_{field}_missing", "message": message, "severity": "error"})
        if eway.transporter_gstin and not self.validate_gstin(eway.transporter_gstin):
            issues.append({"code": "eway_transporter_gstin_invalid", "message": "Transporter GSTIN is invalid.", "severity": "error"})
        if eway.transport_mode == "road" and eway.vehicle_number and not self.validate_vehicle_number(eway.vehicle_number):
            issues.append({"code": "eway_vehicle_invalid", "message": "Vehicle number format is invalid.", "severity": "error"})
        return issues

