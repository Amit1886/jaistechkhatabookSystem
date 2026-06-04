from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.platform.reporting.application.services.analytics_engine import AnalyticsEngine
from apps.platform.reporting.application.services.export_engine import ReportExportEngine
from apps.platform.reporting.application.services.report_engine import ReportEngine
from apps.platform.reporting.application.services.template_seed_service import ReportTemplateSeedService
from apps.platform.reporting.interfaces.api.serializers import (
    AnalyticsMetricSerializer,
    RealtimeDashboardCounterSerializer,
    ReportCategorySerializer,
    ReportExportSerializer,
    ReportRunSerializer,
    ReportTemplateSerializer,
    SavedReportFilterSerializer,
)
from apps.platform.reporting.models import (
    AnalyticsMetric,
    RealtimeDashboardCounter,
    ReportCategory,
    ReportExport,
    ReportRun,
    ReportTemplate,
    SavedReportFilter,
)


class ReportingPermission(permissions.IsAuthenticated):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [ReportingPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class ReportCategoryViewSet(TenantScopedViewSet):
    queryset = ReportCategory.objects.all()
    serializer_class = ReportCategorySerializer


class ReportTemplateViewSet(TenantScopedViewSet):
    queryset = ReportTemplate.objects.select_related("tenant", "category").all()
    serializer_class = ReportTemplateSerializer

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        template = self.get_object()
        result = ReportEngine().run(
            template.key,
            raw_filters=request.data.get("filters") or {},
            tenant=getattr(request, "identity_tenant", None),
            user=request.user,
            page=request.data.get("page", 1),
            page_size=request.data.get("page_size", 50),
        )
        return Response(result)

    @action(detail=True, methods=["post"])
    def export(self, request, pk=None):
        template = self.get_object()
        result = ReportEngine().run(
            template.key,
            raw_filters=request.data.get("filters") or {},
            tenant=getattr(request, "identity_tenant", None),
            user=request.user,
            page=request.data.get("page", 1),
            page_size=request.data.get("page_size", 5000),
        )
        return ReportExportEngine().response(result, request.data.get("format") or "csv")


class SavedReportFilterViewSet(TenantScopedViewSet):
    queryset = SavedReportFilter.objects.select_related("tenant", "template", "user").all()
    serializer_class = SavedReportFilterSerializer


class ReportRunViewSet(TenantScopedViewSet):
    queryset = ReportRun.objects.select_related("tenant", "template", "user").all()
    serializer_class = ReportRunSerializer
    http_method_names = ["get", "head", "options"]


class ReportExportViewSet(TenantScopedViewSet):
    queryset = ReportExport.objects.select_related("tenant", "run").all()
    serializer_class = ReportExportSerializer


class AnalyticsMetricViewSet(TenantScopedViewSet):
    queryset = AnalyticsMetric.objects.select_related("tenant").all()
    serializer_class = AnalyticsMetricSerializer


class RealtimeDashboardCounterViewSet(TenantScopedViewSet):
    queryset = RealtimeDashboardCounter.objects.select_related("tenant").all()
    serializer_class = RealtimeDashboardCounterSerializer


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def run_report(request, key):
    params = request.data if request.method == "POST" else request.query_params
    result = ReportEngine().run(
        key,
        raw_filters=params.get("filters") or params,
        tenant=getattr(request, "identity_tenant", None),
        user=request.user,
        page=params.get("page", 1),
        page_size=params.get("page_size", 50),
    )
    status_code = status.HTTP_404_NOT_FOUND if result.get("error") == "report_not_found" else status.HTTP_200_OK
    return Response(result, status=status_code)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def export_report(request, key):
    result = ReportEngine().run(
        key,
        raw_filters=request.data.get("filters") or {},
        tenant=getattr(request, "identity_tenant", None),
        user=request.user,
        page=request.data.get("page", 1),
        page_size=request.data.get("page_size", 5000),
    )
    return ReportExportEngine().response(result, request.data.get("format") or "csv")


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def analytics_dashboard(request):
    tenant = getattr(request, "identity_tenant", None)
    engine = AnalyticsEngine()
    return Response({"kpis": engine.kpis(tenant), "trends": engine.trends(tenant)})


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def seed_templates(request):
    created = ReportTemplateSeedService().seed(getattr(request, "identity_tenant", None) if request.data.get("tenant_scoped") else None)
    return Response({"created": created})

