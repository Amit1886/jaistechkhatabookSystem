from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from products.models import Category, Product
from products.models import ProductMedia
from vendors.models import Vendor, VendorPaymentGatewayConfig, VendorShippingProviderConfig

from .models import (
    Cart,
    CartItem,
    CustomerAddress,
    CustomerProfile,
    PlatformSettings,
    StoreOrder,
    StoreOrderItem,
    StoreOrderStatusEvent,
    StoreSettlement,
    VendorProductListing,
    Wishlist,
    WishlistItem,
)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "slug", "subdomain", "is_active", "primary_warehouse"]
        read_only_fields = ["id", "slug", "is_active"]


class CategoryPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductPublicSerializer(serializers.ModelSerializer):
    category = CategoryPublicSerializer(read_only=True)
    slug = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    media = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "mrp", "b2c_price", "gst_percent", "description", "is_online", "media"]

    def get_media(self, obj):
        try:
            qs = obj.media.all().order_by("sort_order", "id")
            return ProductMediaSerializer(qs, many=True).data
        except Exception:
            return []


class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ["id", "media_type", "media", "alt_text", "sort_order", "created_at"]
        read_only_fields = ["id", "created_at"]


class VendorProductListingSerializer(serializers.ModelSerializer):
    product = ProductPublicSerializer(read_only=True)
    effective_title = serializers.CharField(read_only=True)
    effective_description = serializers.CharField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = VendorProductListing
        fields = [
            "id",
            "vendor",
            "product",
            "is_online",
            "title",
            "description",
            "price_override",
            "is_featured",
            "effective_title",
            "effective_description",
            "effective_price",
        ]
        read_only_fields = ["id", "vendor", "product"]


class VendorProductListingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProductListing
        fields = ["id", "product", "is_online", "title", "description", "price_override", "is_featured"]
        read_only_fields = ["id"]


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "label",
            "line1",
            "line2",
            "landmark",
            "pincode",
            "district",
            "state",
            "latitude",
            "longitude",
            "alternate_mobile",
            "is_default",
        ]


class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ["id", "full_name", "addresses"]


class CartItemSerializer(serializers.ModelSerializer):
    listing = VendorProductListingSerializer(read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProductListing.objects.all(), source="listing", write_only=True
    )
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "listing", "listing_id", "qty", "unit_price", "line_total"]
        read_only_fields = ["id"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "vendor", "customer", "status", "items", "created_at", "updated_at"]
        read_only_fields = ["id", "vendor", "customer", "created_at", "updated_at"]


class WishlistItemSerializer(serializers.ModelSerializer):
    listing = VendorProductListingSerializer(read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProductListing.objects.all(), source="listing", write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ["id", "listing", "listing_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ["id", "vendor", "customer", "items", "created_at"]
        read_only_fields = ["id", "vendor", "customer", "created_at"]


class StoreOrderItemSerializer(serializers.ModelSerializer):
    product = ProductPublicSerializer(read_only=True)
    listing = VendorProductListingSerializer(read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProductListing.objects.all(), source="listing", write_only=True, required=False, allow_null=True
    )
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source="product", write_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = StoreOrderItem
        fields = ["id", "listing", "listing_id", "product", "product_id", "qty", "unit_price", "line_total"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        listing = attrs.get("listing")
        product = attrs.get("product")
        if listing and product and listing.product_id != product.id:
            raise serializers.ValidationError("listing.product must match product_id")
        return attrs


class StoreOrderStatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreOrderStatusEvent
        fields = ["id", "status", "note", "created_at"]
        read_only_fields = ["id", "created_at"]


class StoreOrderSerializer(serializers.ModelSerializer):
    items = StoreOrderItemSerializer(many=True)
    status_events = StoreOrderStatusEventSerializer(many=True, read_only=True)
    address_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAddress.objects.all(), source="address", write_only=True, allow_null=True, required=False
    )
    address = CustomerAddressSerializer(read_only=True)

    class Meta:
        model = StoreOrder
        fields = [
            "id",
            "vendor",
            "customer",
            "address",
            "address_id",
            "order_number",
            "status",
            "payment_status",
            "subtotal_amount",
            "tax_amount",
            "shipping_amount",
            "discount_amount",
            "total_amount",
            "items",
            "status_events",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor",
            "customer",
            "order_number",
            "status",
            "payment_status",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order: StoreOrder = StoreOrder.objects.create(**validated_data)
        for item in items_data:
            listing = item.get("listing")
            product = item.get("product") or (listing.product if listing else None)
            unit_price = item.get("unit_price")
            if unit_price in (None, "") and listing:
                unit_price = listing.effective_price
            StoreOrderItem.objects.create(
                order=order,
                listing=listing,
                product=product,
                qty=item.get("qty") or 1,
                unit_price=Decimal(str(unit_price or "0.00")),
            )
        order.recalc_totals(save=True)
        StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Order placed")
        return order


class VendorPaymentGatewayConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorPaymentGatewayConfig
        fields = ["id", "vendor", "provider", "is_active", "config", "created_at", "updated_at"]
        read_only_fields = ["id", "vendor", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        cfg = dict(data.get("config") or {})
        # redact common secret keys
        for k in list(cfg.keys()):
            lk = str(k).lower()
            if any(s in lk for s in ["secret", "token", "key", "password"]):
                cfg[k] = "********"
        data["config"] = cfg
        return data


class VendorShippingProviderConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorShippingProviderConfig
        fields = ["id", "vendor", "provider", "is_active", "config", "created_at", "updated_at"]
        read_only_fields = ["id", "vendor", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        cfg = dict(data.get("config") or {})
        for k in list(cfg.keys()):
            lk = str(k).lower()
            if any(s in lk for s in ["secret", "token", "key", "password"]):
                cfg[k] = "********"
        data["config"] = cfg
        return data


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        fields = ["id", "platform_user", "commission_percent", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StoreSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettlement
        fields = [
            "id",
            "order",
            "status",
            "commission_percent",
            "commission_amount",
            "vendor_amount",
            "vendor_wallet_txn_id",
            "platform_wallet_txn_id",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
