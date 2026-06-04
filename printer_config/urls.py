from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PrintEngineRenderAPIView,
    PrintPlaceholderAPIView,
    PrintRenderLogViewSet,
    PrintSettingsAPIView,
    PrintSendAPIView,
    PrintTemplateViewSet,
    PrinterConfigViewSet,
    PrinterTestLogViewSet,
    TemplatePlanAccessViewSet,
    UserPrintTemplateViewSet,
)

router = DefaultRouter()
router.register("configs", PrinterConfigViewSet, basename="printer-config")
router.register("test-logs", PrinterTestLogViewSet, basename="printer-test")
router.register("templates", PrintTemplateViewSet, basename="print-template")
router.register("template-plan-access", TemplatePlanAccessViewSet, basename="template-plan-access")
router.register("user-templates", UserPrintTemplateViewSet, basename="user-print-template")
router.register("render-logs", PrintRenderLogViewSet, basename="print-render-log")

urlpatterns = [
    path("engine/render/", PrintEngineRenderAPIView.as_view(), name="print-engine-render"),
    path("engine/placeholders/", PrintPlaceholderAPIView.as_view(), name="print-placeholder-catalog"),
    path("engine/settings/", PrintSettingsAPIView.as_view(), name="print-engine-settings"),
    path("print/", PrintSendAPIView.as_view(), name="printer-send"),
    path("", include(router.urls)),
]
