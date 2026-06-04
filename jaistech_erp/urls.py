from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("businesses", views.BusinessViewSet, basename="business")
router.register("stores", views.StoreViewSet, basename="store")
router.register("modules", views.ModuleViewSet, basename="module")
router.register("permissions", views.PermissionViewSet, basename="permission")
router.register("roles", views.RoleViewSet, basename="role")
router.register("users", views.MembershipViewSet, basename="membership")
router.register("products", views.ProductViewSet, basename="product")
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("expenses", views.ExpenseViewSet, basename="expense")
router.register("ledger-accounts", views.LedgerAccountViewSet, basename="ledger-account")
router.register("ledger-entries", views.LedgerEntryViewSet, basename="ledger-entry")
router.register("custom-entities", views.CustomEntityViewSet, basename="custom-entity")
router.register("custom-records", views.CustomRecordViewSet, basename="custom-record")
router.register("sync", views.SyncQueueViewSet, basename="sync")

urlpatterns = [
    path("dashboard/", views.dashboard, name="jaistech-dashboard"),
    path("reports/", views.reports, name="jaistech-reports"),
    path("menu/", views.menu, name="jaistech-menu"),
    path("theme/", views.app_bootstrap, name="jaistech-theme"),
    path("settings/", views.app_bootstrap, name="jaistech-settings"),
    path("app/bootstrap/", views.app_bootstrap, name="jaistech-app-bootstrap"),
    path("pos/checkout/", views.pos_checkout, name="jaistech-pos-checkout"),
    path("dynamic/<str:app_label>/<str:model_name>/", views.DynamicModelViewSet.as_view({"get": "list", "post": "create"}), name="jaistech-dynamic-list"),
    path("dynamic/<str:app_label>/<str:model_name>/<int:pk>/", views.DynamicModelViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="jaistech-dynamic-detail"),
]
urlpatterns += router.urls
