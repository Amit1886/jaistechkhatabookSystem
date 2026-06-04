from rest_framework import serializers

from apps.platform.tax_compliance.models import (
    EWayBillRequest,
    GSTInvoice,
    GSTInvoiceLine,
    GSTParty,
    GSTReportSnapshot,
    GSTTaxSlab,
    HSNSACCode,
    PaymentQRProfile,
    TaxAuditLog,
    TaxValidationIssue,
)


class GSTTaxSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTTaxSlab
        fields = "__all__"


class HSNSACCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HSNSACCode
        fields = "__all__"


class GSTPartySerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTParty
        fields = "__all__"


class PaymentQRProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentQRProfile
        fields = "__all__"


class GSTInvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTInvoiceLine
        fields = "__all__"


class GSTInvoiceSerializer(serializers.ModelSerializer):
    lines_detail = GSTInvoiceLineSerializer(source="lines", many=True, read_only=True)
    eway_required = serializers.BooleanField(read_only=True)

    class Meta:
        model = GSTInvoice
        fields = "__all__"


class EWayBillRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = EWayBillRequest
        fields = "__all__"


class TaxValidationIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxValidationIssue
        fields = "__all__"


class TaxAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxAuditLog
        fields = "__all__"
        read_only_fields = fields


class GSTReportSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTReportSnapshot
        fields = "__all__"

