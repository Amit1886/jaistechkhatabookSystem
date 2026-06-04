from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.platform.saas_ecosystem.interfaces.api import views

router = DefaultRouter()
router.register("white-label", views.WhiteLabelProfileViewSet)
router.register("domains", views.TenantDomainViewSet)
router.register("plans", views.SaaSPlanViewSet)
router.register("subscriptions", views.TenantSubscriptionViewSet)
router.register("usage-metrics", views.UsageMetricViewSet)
router.register("usage-records", views.UsageRecordViewSet)
router.register("invoices", views.SaaSInvoiceViewSet)
router.register("payment-retries", views.PaymentRetryViewSet)
router.register("partners", views.EcosystemPartnerViewSet)
router.register("franchise-agreements", views.FranchiseAgreementViewSet)
router.register("routes", views.RoutePlanViewSet)
router.register("salesman-tracking", views.SalesmanTrackingViewSet)
router.register("van-sales", views.VanSalesSessionViewSet)
router.register("deliveries", views.DeliveryAssignmentViewSet)
router.register("warehouse-routes", views.WarehouseRouteViewSet)
router.register("forecasts", views.ForecastModelViewSet)

urlpatterns = [
    path("provision/", views.provision_tenant, name="saas-provision-tenant"),
    path("meter/", views.meter_usage, name="saas-meter-usage"),
]
urlpatterns += router.urls

