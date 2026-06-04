from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.platform.core.interfaces.api import views

router = DefaultRouter()
router.register("industry-blueprints", views.IndustryBlueprintViewSet)
router.register("feature-toggles", views.FeatureToggleViewSet)
router.register("modules", views.ModuleDefinitionViewSet)
router.register("menus", views.MenuItemViewSet)
router.register("forms", views.FormDefinitionViewSet)
router.register("form-fields", views.FormFieldDefinitionViewSet)
router.register("workflows", views.WorkflowDefinitionViewSet)
router.register("workflow-states", views.WorkflowStateViewSet)
router.register("workflow-transitions", views.WorkflowTransitionViewSet)
router.register("reports", views.ReportDefinitionViewSet)
router.register("dashboards", views.DashboardDefinitionViewSet)
router.register("dashboard-widgets", views.DashboardWidgetViewSet)
router.register("event-subscriptions", views.EventSubscriptionViewSet)
router.register("automation-rules", views.AutomationRuleViewSet)
router.register("automation-runs", views.AutomationRunViewSet)
router.register("command-envelopes", views.CommandEnvelopeViewSet)
router.register("background-jobs", views.BackgroundJobDefinitionViewSet)
router.register("products", views.ProductViewSet)
router.register("product-attributes", views.ProductAttributeViewSet)
router.register("product-variants", views.ProductVariantViewSet)
router.register("warehouses", views.WarehouseViewSet)
router.register("stock-ledger", views.StockLedgerEntryViewSet)
router.register("stock-transfers", views.StockTransferViewSet)
router.register("procurement-requests", views.ProcurementRequestViewSet)
router.register("bom", views.BillOfMaterialsViewSet)
router.register("chart-of-accounts", views.ChartOfAccountViewSet)
router.register("journal-entries", views.JournalEntryViewSet)
router.register("journal-lines", views.JournalLineViewSet)
router.register("gst-ledger", views.GSTLedgerEntryViewSet)
router.register("policies", views.PolicyDefinitionViewSet)
router.register("rules", views.RuleDefinitionViewSet)
router.register("query-definitions", views.QueryDefinitionViewSet)
router.register("integration-endpoints", views.IntegrationEndpointViewSet)
router.register("observability-events", views.ObservabilityEventViewSet)

urlpatterns = [
    path("sidebar/", views.sidebar, name="platform-core-sidebar"),
    path("events/publish/", views.publish_event, name="platform-core-publish-event"),
    path("dashboard/", views.engine_dashboard, name="platform-core-dashboard"),
]
urlpatterns += router.urls
