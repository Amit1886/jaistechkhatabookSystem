from apps.platform.tax_compliance.infrastructure.repositories.tax_repository import TaxRepository
from apps.platform.tax_compliance.models import EWayBillRequest, GSTInvoice, GSTReportSnapshot


class GSTReportService:
    def __init__(self, repository=None):
        self.repository = repository or TaxRepository()

    def generate(self, tenant, report_type, period, start_date=None, end_date=None, user=None):
        if report_type == GSTReportSnapshot.ReportType.HSN_SUMMARY:
            data = {"rows": list(self.repository.hsn_summary(tenant, start_date, end_date))}
        elif report_type == GSTReportSnapshot.ReportType.EWAY:
            data = {
                "rows": list(
                    EWayBillRequest.objects.filter(tenant=tenant)
                    .values("invoice__invoice_number", "status", "transporter_name", "vehicle_number", "distance_km", "eway_bill_no")
                    .order_by("-created_at")
                )
            }
        elif report_type == GSTReportSnapshot.ReportType.TRANSPORTER:
            data = {
                "rows": list(
                    EWayBillRequest.objects.filter(tenant=tenant)
                    .values("transporter_name", "transporter_gstin", "transport_mode")
                    .order_by("transporter_name")
                )
            }
        elif report_type in (GSTReportSnapshot.ReportType.SALES_REGISTER, GSTReportSnapshot.ReportType.GSTR1, GSTReportSnapshot.ReportType.GSTR3B):
            data = {
                "summary": self.repository.tax_summary(tenant, start_date, end_date),
                "rows": list(
                    GSTInvoice.objects.filter(tenant=tenant)
                    .values("invoice_number", "invoice_date", "buyer__name", "buyer__gstin", "taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "total_amount")
                    .order_by("invoice_date")
                ),
            }
        else:
            data = {"summary": self.repository.tax_summary(tenant, start_date, end_date)}
        return self.repository.save_report(tenant, report_type, period, data, user=user)

