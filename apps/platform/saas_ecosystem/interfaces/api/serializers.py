from rest_framework import serializers

from apps.platform.saas_ecosystem.models import (
    DeliveryAssignment,
    EcosystemPartner,
    ForecastModel,
    FranchiseAgreement,
    PaymentRetry,
    RoutePlan,
    SaaSInvoice,
    SaaSPlan,
    SalesmanTracking,
    TenantDomain,
    TenantSubscription,
    UsageMetric,
    UsageRecord,
    VanSalesSession,
    WarehouseRoute,
    WhiteLabelProfile,
)


class WhiteLabelProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiteLabelProfile
        fields = "__all__"


class TenantDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = "__all__"


class SaaSPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaaSPlan
        fields = "__all__"


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSubscription
        fields = "__all__"


class UsageMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageMetric
        fields = "__all__"


class UsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRecord
        fields = "__all__"


class SaaSInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaaSInvoice
        fields = "__all__"


class PaymentRetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRetry
        fields = "__all__"


class EcosystemPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcosystemPartner
        fields = "__all__"


class FranchiseAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseAgreement
        fields = "__all__"


class RoutePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutePlan
        fields = "__all__"


class SalesmanTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesmanTracking
        fields = "__all__"


class VanSalesSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VanSalesSession
        fields = "__all__"


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAssignment
        fields = "__all__"


class WarehouseRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseRoute
        fields = "__all__"


class ForecastModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastModel
        fields = "__all__"

