from __future__ import annotations

from rest_framework import serializers

from procurement.models import InvoiceSource, PurchaseDraft, PurchaseDraftItem


class InvoiceSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSource
        fields = [
            "id",
            "source_type",
            "status",
            "external_id",
            "content_type",
            "created_at",
        ]


class PurchaseDraftItemSerializer(serializers.ModelSerializer):
    matched_product_name = serializers.CharField(source="matched_product.name", read_only=True)

    class Meta:
        model = PurchaseDraftItem
        fields = [
            "id",
            "line_no",
            "raw_name",
            "quantity",
            "unit",
            "rate",
            "gst_rate",
            "amount",
            "normalized_quantity",
            "normalized_unit",
            "matched_product",
            "matched_product_name",
            "match_confidence",
            "match_method",
            "requires_review",
            "notes",
        ]


class PurchaseDraftSerializer(serializers.ModelSerializer):
    supplier_name_final = serializers.CharField(source="supplier.name", read_only=True)
    items = PurchaseDraftItemSerializer(many=True, read_only=True)
    source = InvoiceSourceSerializer(read_only=True)

    class Meta:
        model = PurchaseDraft
        fields = [
            "id",
            "source",
            "supplier_name",
            "supplier",
            "supplier_name_final",
            "invoice_number",
            "invoice_date",
            "currency",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "gst_rate",
            "confidence",
            "status",
            "validation_warnings",
            "auto_approved",
            "created_order",
            "created_at",
            "updated_at",
            "items",
        ]

