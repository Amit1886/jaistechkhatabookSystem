from apps.platform.reporting.models import ReportCategory, ReportTemplate


class ReportTemplateSeedService:
    DEFAULTS = [
        ("sales", "Sales", "tax_gst_invoice_sales", "platform_tax.GSTInvoice", ["invoice_number", "invoice_date", "buyer__name", "taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "total_amount"]),
        ("purchase", "Purchase", "tax_gst_purchase", "platform_tax.GSTInvoice", ["invoice_number", "invoice_date", "buyer__name", "taxable_value", "total_amount"]),
        ("inventory", "Inventory", "inventory_products", "platform_core.Product", ["sku", "name", "category", "uom"]),
        ("gst", "GST", "gst_summary", "platform_tax.GSTInvoice", ["invoice_number", "invoice_date", "seller_gstin", "buyer__gstin", "total_amount"]),
        ("accounting", "Accounting", "journal_entries", "platform_core.JournalEntry", ["reference_no", "entry_date", "status", "narration"]),
        ("warehouse", "Warehouse", "warehouse_stock", "platform_core.StockLedgerEntry", ["posted_at", "warehouse__name", "product__name", "quantity", "movement_type"]),
        ("payments", "Payments", "saas_invoices", "platform_saas.SaaSInvoice", ["invoice_number", "status", "subtotal", "tax_amount", "total"]),
        ("subscriptions", "Subscriptions", "tenant_subscriptions", "platform_saas.TenantSubscription", ["tenant__name", "plan__name", "status", "current_period_end"]),
    ]

    def seed(self, tenant=None):
        created = []
        for domain, category_name, key, model, columns in self.DEFAULTS:
            category, _ = ReportCategory.objects.get_or_create(key=domain, defaults={"name": category_name})
            template, was_created = ReportTemplate.objects.get_or_create(
                tenant=tenant,
                key=key,
                defaults={
                    "name": category_name,
                    "category": category,
                    "domain": domain,
                    "source_model": model,
                    "columns": columns,
                    "filters": ["date_from", "date_to", "tenant", "branch", "warehouse", "product", "gst", "status"],
                    "query_spec": {
                        "filter_fields": {
                            "date_from": "created_at",
                            "date_to": "created_at",
                            "status": "status",
                        },
                        "summary": {"total": "total_amount"} if domain in {"sales", "gst"} else {},
                    },
                    "chart_spec": {"group_by": "invoice_date", "value": "total_amount"} if domain in {"sales", "gst"} else {},
                },
            )
            if was_created:
                created.append(template.key)
        return created

