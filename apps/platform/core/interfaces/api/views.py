from django.db.models import Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.platform.core.application.services.event_service import EventService
from apps.platform.core.application.services.metadata_service import MetadataService
from apps.platform.core.application.services.workflow_service import WorkflowError, WorkflowService
from apps.platform.core.infrastructure.repositories.core_repository import CoreRepository
from apps.platform.core.interfaces.api.serializers import (
    AutomationRuleSerializer,
    AutomationRunSerializer,
    BackgroundJobDefinitionSerializer,
    BillOfMaterialsSerializer,
    ChartOfAccountSerializer,
    CommandEnvelopeSerializer,
    DashboardDefinitionSerializer,
    DashboardWidgetSerializer,
    EventSubscriptionSerializer,
    FeatureToggleSerializer,
    FormDefinitionSerializer,
    FormFieldDefinitionSerializer,
    GSTLedgerEntrySerializer,
    IntegrationEndpointSerializer,
    IndustryBlueprintSerializer,
    JournalEntrySerializer,
    JournalLineSerializer,
    MenuItemSerializer,
    ModuleDefinitionSerializer,
    ObservabilityEventSerializer,
    PolicyDefinitionSerializer,
    ProcurementRequestSerializer,
    ProductAttributeSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    QueryDefinitionSerializer,
    ReportDefinitionSerializer,
    RuleDefinitionSerializer,
    StockLedgerEntrySerializer,
    StockTransferSerializer,
    WarehouseSerializer,
    WorkflowDefinitionSerializer,
    WorkflowStateSerializer,
    WorkflowTransitionSerializer,
)
from apps.platform.core.models import (
    AutomationRule,
    AutomationRun,
    BackgroundJobDefinition,
    BillOfMaterials,
    ChartOfAccount,
    CommandEnvelope,
    DashboardDefinition,
    DashboardWidget,
    EventSubscription,
    FeatureToggle,
    FormDefinition,
    FormFieldDefinition,
    GSTLedgerEntry,
    IntegrationEndpoint,
    IndustryBlueprint,
    JournalEntry,
    JournalLine,
    MenuItem,
    ModuleDefinition,
    ObservabilityEvent,
    PolicyDefinition,
    ProcurementRequest,
    Product,
    ProductAttribute,
    ProductVariant,
    QueryDefinition,
    ReportDefinition,
    RuleDefinition,
    StockLedgerEntry,
    StockTransfer,
    Warehouse,
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)


class EnterpriseCorePermission(permissions.IsAdminUser):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [EnterpriseCorePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class IndustryBlueprintViewSet(TenantScopedViewSet):
    queryset = IndustryBlueprint.objects.all()
    serializer_class = IndustryBlueprintSerializer


class FeatureToggleViewSet(TenantScopedViewSet):
    queryset = FeatureToggle.objects.all()
    serializer_class = FeatureToggleSerializer


class ModuleDefinitionViewSet(TenantScopedViewSet):
    queryset = ModuleDefinition.objects.select_related("tenant", "blueprint").all()
    serializer_class = ModuleDefinitionSerializer


class MenuItemViewSet(TenantScopedViewSet):
    queryset = MenuItem.objects.select_related("tenant", "module", "parent").all()
    serializer_class = MenuItemSerializer


class FormDefinitionViewSet(TenantScopedViewSet):
    queryset = FormDefinition.objects.select_related("tenant", "module").prefetch_related("fields").all()
    serializer_class = FormDefinitionSerializer

    @action(detail=False, methods=["get"], url_path="schema/(?P<key>[^/.]+)")
    def schema(self, request, key=None):
        schema = MetadataService().form_schema(key, request.user, getattr(request, "identity_tenant", None))
        if not schema:
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(schema)


class FormFieldDefinitionViewSet(TenantScopedViewSet):
    queryset = FormFieldDefinition.objects.select_related("form").all()
    serializer_class = FormFieldDefinitionSerializer


class WorkflowDefinitionViewSet(TenantScopedViewSet):
    queryset = WorkflowDefinition.objects.select_related("tenant", "module").prefetch_related("states", "transitions").all()
    serializer_class = WorkflowDefinitionSerializer

    @action(detail=False, methods=["post"], url_path="transition")
    def transition(self, request):
        try:
            result = WorkflowService().transition(
                workflow_key=request.data.get("workflow"),
                transition_key=request.data.get("transition"),
                current_state=request.data.get("current_state"),
                payload=request.data.get("payload") or {},
                user=request.user,
                tenant=getattr(request, "identity_tenant", None),
            )
            return Response(result)
        except WorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class WorkflowStateViewSet(TenantScopedViewSet):
    queryset = WorkflowState.objects.select_related("workflow").all()
    serializer_class = WorkflowStateSerializer


class WorkflowTransitionViewSet(TenantScopedViewSet):
    queryset = WorkflowTransition.objects.select_related("workflow").all()
    serializer_class = WorkflowTransitionSerializer


class ReportDefinitionViewSet(TenantScopedViewSet):
    queryset = ReportDefinition.objects.select_related("tenant", "module").all()
    serializer_class = ReportDefinitionSerializer


class DashboardDefinitionViewSet(TenantScopedViewSet):
    queryset = DashboardDefinition.objects.prefetch_related("widgets").all()
    serializer_class = DashboardDefinitionSerializer


class DashboardWidgetViewSet(TenantScopedViewSet):
    queryset = DashboardWidget.objects.select_related("dashboard").all()
    serializer_class = DashboardWidgetSerializer


class EventSubscriptionViewSet(TenantScopedViewSet):
    queryset = EventSubscription.objects.all()
    serializer_class = EventSubscriptionSerializer


class AutomationRuleViewSet(TenantScopedViewSet):
    queryset = AutomationRule.objects.select_related("tenant", "run_as").all()
    serializer_class = AutomationRuleSerializer


class AutomationRunViewSet(TenantScopedViewSet):
    queryset = AutomationRun.objects.select_related("tenant", "rule").all()
    serializer_class = AutomationRunSerializer
    http_method_names = ["get", "head", "options"]


class CommandEnvelopeViewSet(TenantScopedViewSet):
    queryset = CommandEnvelope.objects.select_related("tenant", "requested_by").all()
    serializer_class = CommandEnvelopeSerializer
    http_method_names = ["get", "head", "options"]


class BackgroundJobDefinitionViewSet(TenantScopedViewSet):
    queryset = BackgroundJobDefinition.objects.all()
    serializer_class = BackgroundJobDefinitionSerializer


class ProductViewSet(TenantScopedViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class ProductAttributeViewSet(TenantScopedViewSet):
    queryset = ProductAttribute.objects.all()
    serializer_class = ProductAttributeSerializer


class ProductVariantViewSet(TenantScopedViewSet):
    queryset = ProductVariant.objects.select_related("tenant", "product").all()
    serializer_class = ProductVariantSerializer


class WarehouseViewSet(TenantScopedViewSet):
    queryset = Warehouse.objects.select_related("tenant", "company", "branch").all()
    serializer_class = WarehouseSerializer


class StockLedgerEntryViewSet(TenantScopedViewSet):
    queryset = StockLedgerEntry.objects.select_related("tenant", "warehouse", "product", "variant").all()
    serializer_class = StockLedgerEntrySerializer
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"])
    def balance(self, request):
        tenant = getattr(request, "identity_tenant", None)
        if tenant is None:
            return Response([])
        rows = CoreRepository().stock_balance(tenant)
        return Response(list(rows))


class StockTransferViewSet(TenantScopedViewSet):
    queryset = StockTransfer.objects.select_related("tenant", "source_warehouse", "destination_warehouse").all()
    serializer_class = StockTransferSerializer


class ProcurementRequestViewSet(TenantScopedViewSet):
    queryset = ProcurementRequest.objects.all()
    serializer_class = ProcurementRequestSerializer


class BillOfMaterialsViewSet(TenantScopedViewSet):
    queryset = BillOfMaterials.objects.select_related("tenant", "product").all()
    serializer_class = BillOfMaterialsSerializer


class ChartOfAccountViewSet(TenantScopedViewSet):
    queryset = ChartOfAccount.objects.select_related("tenant", "parent").all()
    serializer_class = ChartOfAccountSerializer


class JournalEntryViewSet(TenantScopedViewSet):
    queryset = JournalEntry.objects.select_related("tenant", "posted_by").prefetch_related("lines").all()
    serializer_class = JournalEntrySerializer


class JournalLineViewSet(TenantScopedViewSet):
    queryset = JournalLine.objects.select_related("journal", "account").all()
    serializer_class = JournalLineSerializer


class GSTLedgerEntryViewSet(TenantScopedViewSet):
    queryset = GSTLedgerEntry.objects.select_related("tenant", "journal").all()
    serializer_class = GSTLedgerEntrySerializer


class PolicyDefinitionViewSet(TenantScopedViewSet):
    queryset = PolicyDefinition.objects.all()
    serializer_class = PolicyDefinitionSerializer


class RuleDefinitionViewSet(TenantScopedViewSet):
    queryset = RuleDefinition.objects.all()
    serializer_class = RuleDefinitionSerializer


class QueryDefinitionViewSet(TenantScopedViewSet):
    queryset = QueryDefinition.objects.all()
    serializer_class = QueryDefinitionSerializer


class IntegrationEndpointViewSet(TenantScopedViewSet):
    queryset = IntegrationEndpoint.objects.all()
    serializer_class = IntegrationEndpointSerializer


class ObservabilityEventViewSet(TenantScopedViewSet):
    queryset = ObservabilityEvent.objects.all()
    serializer_class = ObservabilityEventSerializer
    http_method_names = ["get", "head", "options"]


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def sidebar(request):
    return Response(MetadataService().sidebar_for_user(request.user, getattr(request, "identity_tenant", None)))


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def publish_event(request):
    result = EventService().publish(
        event_type=request.data.get("event_type"),
        payload=request.data.get("payload") or {},
        tenant=getattr(request, "identity_tenant", None),
        user=request.user,
        topic=request.data.get("topic") or "erp.core",
        key=request.data.get("key") or "",
    )
    return Response(result)


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def engine_dashboard(request):
    return Response(
        {
            "modules": ModuleDefinition.objects.count(),
            "menus": MenuItem.objects.count(),
            "workflows": WorkflowDefinition.objects.count(),
            "automations": list(AutomationRule.objects.values("status").annotate(total=Count("id"))),
            "products": Product.objects.count(),
            "journals": JournalEntry.objects.count(),
        }
    )
    CommandEnvelopeSerializer,
    CommandEnvelope,
