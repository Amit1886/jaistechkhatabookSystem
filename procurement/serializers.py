from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from khataapp.models import Party
from procurement.models import SupplierPriceHistory, SupplierProduct, SupplierRating


class SupplierSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    class Meta:
        model = Party
        fields = [
            "id",
            "name",
            "mobile",
            "email",
            "address",
            "whatsapp_number",
            "is_active",
            "avg_rating",
            "rating_count",
        ]

    def _rating_info(self, obj):
        rating_map = self.context.get("rating_map") or {}
        return rating_map.get(int(obj.id), {}) if obj and getattr(obj, "id", None) else {}

    def get_avg_rating(self, obj):
        info = self._rating_info(obj)
        val = info.get("avg") or Decimal("0.00")
        try:
            return str(Decimal(str(val)).quantize(Decimal("0.01")))
        except Exception:
            return "0.00"

    def get_rating_count(self, obj):
        info = self._rating_info(obj)
        try:
            return int(info.get("count") or 0)
        except Exception:
            return 0


class SupplierProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SupplierProduct
        fields = [
            "id",
            "owner",
            "supplier",
            "supplier_name",
            "product",
            "product_name",
            "product_sku",
            "price",
            "moq",
            "delivery_days",
            "last_updated",
            "is_active",
        ]
        read_only_fields = ["owner", "last_updated"]


class SupplierPriceHistorySerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SupplierPriceHistory
        fields = [
            "id",
            "owner",
            "supplier",
            "supplier_name",
            "product",
            "product_name",
            "product_sku",
            "old_price",
            "new_price",
            "change_pct",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = ["owner", "updated_at"]


class SupplierRatingSerializer(serializers.ModelSerializer):
    avg = serializers.SerializerMethodField()

    class Meta:
        model = SupplierRating
        fields = [
            "id",
            "owner",
            "supplier",
            "rated_by",
            "delivery_speed",
            "product_quality",
            "pricing",
            "comment",
            "avg",
            "updated_at",
        ]
        read_only_fields = ["owner", "rated_by", "updated_at"]

    def get_avg(self, obj):
        try:
            return str(obj.average.quantize(Decimal("0.01")))
        except Exception:
            return "0.00"

