from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.platform.reporting.interfaces.api import views

router = DefaultRouter()
router.register("categories", views.ReportCategoryViewSet)
router.register("templates", views.ReportTemplateViewSet)
router.register("saved-filters", views.SavedReportFilterViewSet)
router.register("runs", views.ReportRunViewSet)
router.register("exports", views.ReportExportViewSet)
router.register("metrics", views.AnalyticsMetricViewSet)
router.register("realtime-counters", views.RealtimeDashboardCounterViewSet)

urlpatterns = [
    path("run/<slug:key>/", views.run_report, name="platform-report-run"),
    path("export/<slug:key>/", views.export_report, name="platform-report-export"),
    path("dashboard/", views.analytics_dashboard, name="platform-report-dashboard"),
    path("seed/", views.seed_templates, name="platform-report-seed"),
]
urlpatterns += router.urls

