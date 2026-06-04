from django.apps import apps
from rest_framework import serializers

from . import models


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Business
        fields = "__all__"


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Store
        fields = "__all__"


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Module
        fields = "__all__"


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Permission
        fields = "__all__"


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Role
        fields = "__all__"


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserBusinessMembership
        fields = "__all__"


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Customer
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = models.Product
        fields = "__all__"


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.InvoiceLine
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, required=False)

    class Meta:
        model = models.Invoice
        fields = "__all__"

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        invoice = models.Invoice.objects.create(**validated_data)
        for line in lines:
            models.InvoiceLine.objects.create(invoice=invoice, **line)
        invoice.recalculate()
        invoice.save(update_fields=["subtotal", "tax_total", "grand_total"])
        return invoice


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Expense
        fields = "__all__"


class LedgerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LedgerAccount
        fields = "__all__"


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LedgerEntry
        fields = "__all__"


class CustomEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomEntity
        fields = "__all__"


class CustomRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomRecord
        fields = "__all__"


class SyncQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SyncQueue
        fields = "__all__"


def serializer_for_model(model):
    class DynamicSerializer(serializers.ModelSerializer):
        class Meta:
            fields = "__all__"

    DynamicSerializer.Meta.model = model
    DynamicSerializer.__name__ = f"{model.__name__}DynamicSerializer"
    return DynamicSerializer


def dynamic_model_choices():
    allowed_apps = {"jaistech_erp", "products", "orders", "commerce", "pos", "warehouse", "crm", "billing"}
    return [
        f"{model._meta.app_label}.{model._meta.model_name}"
        for model in apps.get_models()
        if model._meta.app_label in allowed_apps and not model._meta.abstract
    ]

