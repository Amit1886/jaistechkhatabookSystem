from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.platform.saas_ecosystem.application.services.billing_service import SaaSBillingService
from apps.platform.saas_ecosystem.application.services.provisioning_service import TenantProvisioningService
from apps.platform.saas_ecosystem.interfaces.api.serializers import (
    DeliveryAssignmentSerializer,
    EcosystemPartnerSerializer,
    ForecastModelSerializer,
    FranchiseAgreementSerializer,
    PaymentRetrySerializer,
    RoutePlanSerializer,
    SaaSInvoiceSerializer,
    SaaSPlanSerializer,
    SalesmanTrackingSerializer,
    TenantDomainSerializer,
    TenantSubscriptionSerializer,
    UsageMetricSerializer,
    UsageRecordSerializer,
    VanSalesSessionSerializer,
    WarehouseRouteSerializer,
    WhiteLabelProfileSerializer,
)
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


class SaaSAdminPermission(permissions.IsAdminUser):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [SaaSAdminPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class WhiteLabelProfileViewSet(TenantScopedViewSet):
    queryset = WhiteLabelProfile.objects.select_related("tenant").all()
    serializer_class = WhiteLabelProfileSerializer


class TenantDomainViewSet(TenantScopedViewSet):
    queryset = TenantDomain.objects.select_related("tenant").all()
    serializer_class = TenantDomainSerializer


class SaaSPlanViewSet(TenantScopedViewSet):
    queryset = SaaSPlan.objects.all()
    serializer_class = SaaSPlanSerializer


class TenantSubscriptionViewSet(TenantScopedViewSet):
    queryset = TenantSubscription.objects.select_related("tenant", "plan").all()
    serializer_class = TenantSubscriptionSerializer


class UsageMetricViewSet(TenantScopedViewSet):
    queryset = UsageMetric.objects.all()
    serializer_class = UsageMetricSerializer


class UsageRecordViewSet(TenantScopedViewSet):
    queryset = UsageRecord.objects.select_related("tenant", "metric").all()
    serializer_class = UsageRecordSerializer


class SaaSInvoiceViewSet(TenantScopedViewSet):
    queryset = SaaSInvoice.objects.select_related("tenant", "subscription").all()
    serializer_class = SaaSInvoiceSerializer

    @action(detail=False, methods=["post"])
    def generate(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
        invoice = SaaSBillingService().generate_invoice(tenant)
        if not invoice:
            return Response({"detail": "No active subscription."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(invoice).data)


class PaymentRetryViewSet(TenantScopedViewSet):
    queryset = PaymentRetry.objects.select_related("tenant", "invoice").all()
    serializer_class = PaymentRetrySerializer


class EcosystemPartnerViewSet(TenantScopedViewSet):
    queryset = EcosystemPartner.objects.select_related("tenant", "parent", "company", "branch", "contact_user").all()
    serializer_class = EcosystemPartnerSerializer


class FranchiseAgreementViewSet(TenantScopedViewSet):
    queryset = FranchiseAgreement.objects.select_related("tenant", "partner").all()
    serializer_class = FranchiseAgreementSerializer


class RoutePlanViewSet(TenantScopedViewSet):
    queryset = RoutePlan.objects.select_related("tenant", "owner", "salesman").all()
    serializer_class = RoutePlanSerializer


class SalesmanTrackingViewSet(TenantScopedViewSet):
    queryset = SalesmanTracking.objects.select_related("tenant", "salesman", "route").all()
    serializer_class = SalesmanTrackingSerializer


class VanSalesSessionViewSet(TenantScopedViewSet):
    queryset = VanSalesSession.objects.select_related("tenant", "route", "salesman").all()
    serializer_class = VanSalesSessionSerializer


class DeliveryAssignmentViewSet(TenantScopedViewSet):
    queryset = DeliveryAssignment.objects.select_related("tenant", "route", "delivery_user").all()
    serializer_class = DeliveryAssignmentSerializer


class WarehouseRouteViewSet(TenantScopedViewSet):
    queryset = WarehouseRoute.objects.select_related("tenant", "source_branch", "destination_branch").all()
    serializer_class = WarehouseRouteSerializer


class ForecastModelViewSet(TenantScopedViewSet):
    queryset = ForecastModel.objects.select_related("tenant").all()
    serializer_class = ForecastModelSerializer


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def provision_tenant(request):
    plan = None
    plan_key = request.data.get("plan_key")
    if plan_key:
        plan = SaaSPlan.objects.filter(key=plan_key, is_active=True).first()
    result = TenantProvisioningService().provision(
        name=request.data.get("name"),
        owner_email=request.data.get("owner_email", ""),
        plan=plan,
        branding=request.data.get("branding") or {},
    )
    return Response(
        {
            "tenant_id": str(result["tenant"].id),
            "company_id": str(result["company"].id),
            "branch_id": str(result["branch"].id),
            "subscription_id": str(result["subscription"].id) if result["subscription"] else None,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def meter_usage(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    usage = SaaSBillingService().meter(
        tenant,
        request.data.get("metric_key"),
        request.data.get("quantity", 1),
        request.data.get("source_type", ""),
        request.data.get("source_id", ""),
    )
    return Response(UsageRecordSerializer(usage).data, status=status.HTTP_201_CREATED)

