from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.platform.tax_compliance.interfaces.api import views

router = DefaultRouter()
router.register("tax-slabs", views.GSTTaxSlabViewSet)
router.register("hsn-sac", views.HSNSACCodeViewSet)
router.register("parties", views.GSTPartyViewSet)
router.register("payment-profiles", views.PaymentQRProfileViewSet)
router.register("invoices", views.GSTInvoiceViewSet)
router.register("invoice-lines", views.GSTInvoiceLineViewSet)
router.register("eway-bills", views.EWayBillRequestViewSet)
router.register("validation-issues", views.TaxValidationIssueViewSet)
router.register("audit-logs", views.TaxAuditLogViewSet)
router.register("report-snapshots", views.GSTReportSnapshotViewSet)

urlpatterns = [
    path("reports/generate/", views.generate_report, name="tax-generate-report"),
]
urlpatterns += router.urls

