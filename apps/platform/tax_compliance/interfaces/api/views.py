from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.platform.tax_compliance.application.services.eway_service import EWayBillService
from apps.platform.tax_compliance.application.services.gst_service import GSTService
from apps.platform.tax_compliance.application.services.invoice_print_service import InvoicePrintService
from apps.platform.tax_compliance.application.services.payment_qr_service import PaymentQRService
from apps.platform.tax_compliance.application.services.report_service import GSTReportService
from apps.platform.tax_compliance.interfaces.api.serializers import (
    EWayBillRequestSerializer,
    GSTInvoiceLineSerializer,
    GSTInvoiceSerializer,
    GSTPartySerializer,
    GSTReportSnapshotSerializer,
    GSTTaxSlabSerializer,
    HSNSACCodeSerializer,
    PaymentQRProfileSerializer,
    TaxAuditLogSerializer,
    TaxValidationIssueSerializer,
)
from apps.platform.tax_compliance.models import (
    EWayBillRequest,
    GSTInvoice,
    GSTInvoiceLine,
    GSTParty,
    GSTReportSnapshot,
    GSTTaxSlab,
    HSNSACCode,
    PaymentQRProfile,
    TaxAuditLog,
    TaxValidationIssue,
)


class TaxAdminPermission(permissions.IsAdminUser):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [TaxAdminPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class GSTTaxSlabViewSet(TenantScopedViewSet):
    queryset = GSTTaxSlab.objects.all()
    serializer_class = GSTTaxSlabSerializer


class HSNSACCodeViewSet(TenantScopedViewSet):
    queryset = HSNSACCode.objects.select_related("tax_slab").all()
    serializer_class = HSNSACCodeSerializer


class GSTPartyViewSet(TenantScopedViewSet):
    queryset = GSTParty.objects.select_related("tenant").all()
    serializer_class = GSTPartySerializer


class PaymentQRProfileViewSet(TenantScopedViewSet):
    queryset = PaymentQRProfile.objects.select_related("tenant").all()
    serializer_class = PaymentQRProfileSerializer


class GSTInvoiceViewSet(TenantScopedViewSet):
    queryset = GSTInvoice.objects.select_related("tenant", "buyer", "payment_profile").prefetch_related("lines").all()
    serializer_class = GSTInvoiceSerializer

    @action(detail=True, methods=["post"])
    def validate_gst(self, request, pk=None):
        result = GSTService().validate_invoice(self.get_object(), user=request.user)
        return Response(
            {
                "invoice": self.get_serializer(result["invoice"]).data,
                "issues": result["issues"],
                "eway_required": result["eway_required"],
                "eway_fields": EWayBillService().required_fields_prompt() if result["eway_required"] else [],
            }
        )

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        result = GSTService().issue_invoice(self.get_object(), user=request.user)
        return Response({"invoice": self.get_serializer(result["invoice"]).data, "issues": result["issues"]})

    @action(detail=True, methods=["get"])
    def payment_qr(self, request, pk=None):
        return Response(PaymentQRService().invoice_payment_block(self.get_object()))

    @action(detail=True, methods=["get"])
    def print_context(self, request, pk=None):
        copy_type = request.query_params.get("copy", "customer")
        layout = request.query_params.get("layout", "a4")
        context = InvoicePrintService().render_context(self.get_object(), copy_type=copy_type, layout=layout)
        return Response(
            {
                "layout": context["layout"],
                "copy_type": context["copy_type"],
                "payment": context["payment"],
                "supported_layouts": context["supported_layouts"],
                "invoice_id": str(context["invoice"].id),
                "eway_id": str(context["eway"].id) if context["eway"] else None,
            }
        )


class GSTInvoiceLineViewSet(TenantScopedViewSet):
    queryset = GSTInvoiceLine.objects.select_related("invoice", "hsn_sac").all()
    serializer_class = GSTInvoiceLineSerializer


class EWayBillRequestViewSet(TenantScopedViewSet):
    queryset = EWayBillRequest.objects.select_related("tenant", "invoice").all()
    serializer_class = EWayBillRequestSerializer

    @action(detail=True, methods=["post"])
    def prepare(self, request, pk=None):
        result = EWayBillService().prepare(self.get_object().invoice, **request.data)
        return Response({"eway": self.get_serializer(result["eway"]).data, "issues": result["issues"]})

    @action(detail=True, methods=["post"])
    def mark_generated(self, request, pk=None):
        eway = EWayBillService().mark_generated(self.get_object(), request.data.get("eway_bill_no", ""))
        return Response(self.get_serializer(eway).data)


class TaxValidationIssueViewSet(TenantScopedViewSet):
    queryset = TaxValidationIssue.objects.select_related("tenant", "invoice").all()
    serializer_class = TaxValidationIssueSerializer


class TaxAuditLogViewSet(TenantScopedViewSet):
    queryset = TaxAuditLog.objects.select_related("tenant", "actor", "invoice").all()
    serializer_class = TaxAuditLogSerializer
    http_method_names = ["get", "head", "options"]


class GSTReportSnapshotViewSet(TenantScopedViewSet):
    queryset = GSTReportSnapshot.objects.select_related("tenant", "generated_by").all()
    serializer_class = GSTReportSnapshotSerializer


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def generate_report(request):
    tenant = getattr(request, "identity_tenant", None)
    if tenant is None:
        return Response({"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST)
    snapshot = GSTReportService().generate(
        tenant=tenant,
        report_type=request.data.get("report_type"),
        period=request.data.get("period"),
        start_date=request.data.get("start_date"),
        end_date=request.data.get("end_date"),
        user=request.user,
    )
    return Response(GSTReportSnapshotSerializer(snapshot).data)

