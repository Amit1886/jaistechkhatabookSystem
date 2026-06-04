from django.db.models import Sum

from apps.platform.tax_compliance.models import (
    EWayBillRequest,
    GSTInvoice,
    GSTInvoiceLine,
    GSTReportSnapshot,
    TaxAuditLog,
    TaxValidationIssue,
)


class TaxRepository:
    def save_invoice_totals(self, invoice, totals):
        for field, value in totals.items():
            setattr(invoice, field, value)
        invoice.save(update_fields=[*totals.keys(), "updated_at"])
        return invoice

    def replace_validation_issues(self, invoice, issues):
        TaxValidationIssue.objects.filter(invoice=invoice, resolved_at__isnull=True).delete()
        return [
            TaxValidationIssue.objects.create(tenant=invoice.tenant, invoice=invoice, **issue)
            for issue in issues
        ]

    def eway_for_invoice(self, invoice):
        obj, _ = EWayBillRequest.objects.get_or_create(tenant=invoice.tenant, invoice=invoice)
        return obj

    def audit(self, *, tenant, invoice=None, actor=None, action="", before=None, after=None, ip_address=None):
        return TaxAuditLog.objects.create(
            tenant=tenant,
            invoice=invoice,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            before=before or {},
            after=after or {},
            ip_address=ip_address,
        )

    def tax_summary(self, tenant, start_date=None, end_date=None):
        qs = GSTInvoice.objects.filter(tenant=tenant).exclude(status=GSTInvoice.Status.CANCELLED)
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        return qs.aggregate(
            taxable_value=Sum("taxable_value"),
            cgst=Sum("cgst_amount"),
            sgst=Sum("sgst_amount"),
            igst=Sum("igst_amount"),
            cess=Sum("cess_amount"),
            total=Sum("total_amount"),
        )

    def hsn_summary(self, tenant, start_date=None, end_date=None):
        qs = GSTInvoiceLine.objects.filter(invoice__tenant=tenant).exclude(invoice__status=GSTInvoice.Status.CANCELLED)
        if start_date:
            qs = qs.filter(invoice__invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice__invoice_date__lte=end_date)
        return qs.values("hsn_sac__code", "hsn_sac__description").annotate(
            quantity=Sum("quantity"),
            taxable_value=Sum("taxable_value"),
            cgst=Sum("cgst_amount"),
            sgst=Sum("sgst_amount"),
            igst=Sum("igst_amount"),
            cess=Sum("cess_amount"),
        ).order_by("hsn_sac__code")

    def save_report(self, tenant, report_type, period, data, user=None):
        snapshot, _ = GSTReportSnapshot.objects.update_or_create(
            tenant=tenant,
            report_type=report_type,
            period=period,
            defaults={"data": data, "generated_by": user if getattr(user, "is_authenticated", False) else None},
        )
        return snapshot

