from django.db.models import Count, Sum


class AnalyticsEngine:
    def kpis(self, tenant=None):
        data = {}
        try:
            from apps.platform.core.models import Product, StockLedgerEntry

            products = Product.objects.all()
            stock = StockLedgerEntry.objects.all()
            if tenant:
                products = products.filter(tenant=tenant)
                stock = stock.filter(tenant=tenant)
            data["products"] = products.count()
            data["stock_quantity"] = stock.aggregate(total=Sum("quantity")).get("total") or 0
        except Exception:
            data["products"] = 0
            data["stock_quantity"] = 0
        try:
            from apps.platform.tax_compliance.models import GSTInvoice

            invoices = GSTInvoice.objects.all()
            if tenant:
                invoices = invoices.filter(tenant=tenant)
            data["sales_total"] = invoices.aggregate(total=Sum("total_amount")).get("total") or 0
            data["invoice_count"] = invoices.count()
        except Exception:
            data["sales_total"] = 0
            data["invoice_count"] = 0
        return data

    def trends(self, tenant=None):
        try:
            from apps.platform.tax_compliance.models import GSTInvoice

            qs = GSTInvoice.objects.all()
            if tenant:
                qs = qs.filter(tenant=tenant)
            rows = qs.values("invoice_date").annotate(total=Sum("total_amount"), count=Count("id")).order_by("invoice_date")[:90]
            return {"sales": list(rows)}
        except Exception:
            return {"sales": []}

