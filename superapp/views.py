from decimal import Decimal

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from superapp import models
from superapp import serializers
from superapp.services.dashboard import build_super_dashboard_snapshot
from superapp.services.expense_scanner import process_expense_scan
from superapp.services.restaurant_engine import create_table_order, update_order_status
from superapp.services.tax_engine import build_tax_report, create_einvoice_ready_payload, split_gst, suggest_tax_rate, validate_invoice_payload
from superapp.services.wallet_engine import calculate_cashback, calculate_emi, post_wallet_entry


class OwnerScopedMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return qs
        model = qs.model
        if hasattr(model, "owner"):
            return qs.filter(owner=user)
        if hasattr(model, "customer"):
            return qs.filter(customer=user)
        if hasattr(model, "generated_by"):
            return qs.filter(generated_by=user)
        return qs


class BusinessUnitViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.BusinessUnit.objects.select_related("owner").all()
    serializer_class = serializers.BusinessUnitSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SuperAppModuleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.SuperAppModule.objects.filter(is_enabled=True)
    serializer_class = serializers.SuperAppModuleSerializer
    permission_classes = [permissions.IsAuthenticated]


class CustomerWalletViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.CustomerWallet.objects.select_related("customer", "business_unit").all()
    serializer_class = serializers.CustomerWalletSerializer

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

    @action(detail=False, methods=["post"])
    def credit(self, request):
        wallet = post_wallet_entry(
            request.user,
            Decimal(str(request.data.get("amount") or "0")),
            bucket=request.data.get("bucket") or models.WalletTransaction.Bucket.STORE_CREDIT,
            entry_type=models.WalletTransaction.EntryType.CREDIT,
            source=request.data.get("source") or "manual",
            channel=request.data.get("channel") or "pos",
            reference=request.data.get("reference") or "",
            metadata=request.data.get("metadata") or {},
            points=int(request.data.get("points") or 0),
        )
        return Response(serializers.CustomerWalletSerializer(wallet, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def redeem(self, request):
        try:
            wallet = post_wallet_entry(
                request.user,
                Decimal(str(request.data.get("amount") or "0")),
                bucket=request.data.get("bucket") or models.WalletTransaction.Bucket.STORE_CREDIT,
                entry_type=models.WalletTransaction.EntryType.DEBIT,
                source="checkout_redeem",
                channel=request.data.get("channel") or "pos",
                reference=request.data.get("reference") or "",
                metadata=request.data.get("metadata") or {},
                points=-abs(int(request.data.get("points") or 0)),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.CustomerWalletSerializer(wallet, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def cashback_preview(self, request):
        amount = Decimal(str(request.data.get("amount") or "0"))
        cashback = calculate_cashback(amount, channel=request.data.get("channel") or "", tier=request.data.get("tier") or "")
        return Response({"amount": str(amount), "cashback": str(cashback)})

    @action(detail=False, methods=["post"])
    def emi_calculator(self, request):
        installment = calculate_emi(
            Decimal(str(request.data.get("principal_amount") or "0")),
            Decimal(str(request.data.get("interest_rate") or "0")),
            int(request.data.get("tenure_months") or 1),
        )
        return Response({"monthly_installment": str(installment)})


class WalletTransactionViewSet(OwnerScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = models.WalletTransaction.objects.select_related("wallet", "wallet__customer").all()
    serializer_class = serializers.WalletTransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(wallet__customer=self.request.user)


class CashbackRuleViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.CashbackRule.objects.select_related("business_unit").all()
    serializer_class = serializers.CashbackRuleSerializer


class GiftCardViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.GiftCard.objects.select_related("issued_to").all()
    serializer_class = serializers.GiftCardSerializer


class EMIPlanViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.EMIPlan.objects.select_related("customer").all()
    serializer_class = serializers.EMIPlanSerializer

    def perform_create(self, serializer):
        principal = serializer.validated_data["principal_amount"]
        rate = serializer.validated_data.get("interest_rate") or Decimal("0")
        months = serializer.validated_data.get("tenure_months") or 1
        serializer.save(customer=self.request.user, monthly_installment=calculate_emi(principal, rate, months))


class ReferralBonusViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.ReferralBonus.objects.select_related("referrer", "referred", "wallet").all()
    serializer_class = serializers.ReferralBonusSerializer


class TaxRuleViewSet(viewsets.ModelViewSet):
    queryset = models.TaxRule.objects.all()
    serializer_class = serializers.TaxRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def suggest(self, request):
        rate = suggest_tax_rate(hsn_sac=request.query_params.get("hsn_sac") or "", product_category=request.query_params.get("product_category") or "")
        return Response({"gst_rate": str(rate)})

    @action(detail=False, methods=["post"])
    def split(self, request):
        data = split_gst(
            Decimal(str(request.data.get("taxable_value") or "0")),
            Decimal(str(request.data.get("gst_rate") or "0")),
            seller_state_code=request.data.get("seller_state_code") or "",
            buyer_state_code=request.data.get("buyer_state_code") or "",
        )
        return Response({k: str(v) for k, v in data.items()})


class GSTCategoryViewSet(viewsets.ModelViewSet):
    queryset = models.GSTCategory.objects.all()
    serializer_class = serializers.GSTCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class EInvoiceViewSet(viewsets.ModelViewSet):
    queryset = models.EInvoice.objects.all()
    serializer_class = serializers.EInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def validate_payload(self, request):
        alerts = validate_invoice_payload(request.data)
        return Response(serializers.TaxAlertSerializer(alerts, many=True).data)

    @action(detail=False, methods=["post"])
    def create_ready(self, request):
        invoice = create_einvoice_ready_payload(request.data)
        return Response(serializers.EInvoiceSerializer(invoice, context={"request": request}).data, status=status.HTTP_201_CREATED)


class TaxAlertViewSet(viewsets.ModelViewSet):
    queryset = models.TaxAlert.objects.all()
    serializer_class = serializers.TaxAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        obj = self.get_object()
        obj.resolved_at = timezone.now()
        obj.save(update_fields=["resolved_at", "updated_at"])
        return Response(serializers.TaxAlertSerializer(obj, context={"request": request}).data)


class TaxReportViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.TaxReport.objects.select_related("generated_by").all()
    serializer_class = serializers.TaxReportSerializer

    @action(detail=False, methods=["post"])
    def generate(self, request):
        report = build_tax_report(request.data.get("report_type") or "tax_summary", request.data.get("period") or timezone.now().strftime("%Y-%m"), user=request.user)
        return Response(serializers.TaxReportSerializer(report, context={"request": request}).data)


class ExpenseScanViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.ExpenseScan.objects.select_related("owner", "business_unit", "duplicate_of").all()
    serializer_class = serializers.ExpenseScanSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        scan = process_expense_scan(self.get_object(), raw_text=request.data.get("raw_text") or "")
        return Response(serializers.ExpenseScanSerializer(scan, context={"request": request}).data)


class ExpenseApprovalViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.ExpenseApproval.objects.select_related("expense_scan", "approver").all()
    serializer_class = serializers.ExpenseApprovalSerializer

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        obj = self.get_object()
        obj.status = request.data.get("status") or "approved"
        obj.note = request.data.get("note") or obj.note
        obj.approver = request.user
        obj.decided_at = timezone.now()
        obj.save()
        return Response(serializers.ExpenseApprovalSerializer(obj, context={"request": request}).data)


class RestaurantTableViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.RestaurantTable.objects.select_related("business_unit").all()
    serializer_class = serializers.RestaurantTableSerializer


class MenuCategoryViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.MenuCategory.objects.select_related("business_unit").all()
    serializer_class = serializers.MenuCategorySerializer


class MenuItemViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.MenuItem.objects.select_related("category", "category__business_unit").all()
    serializer_class = serializers.MenuItemSerializer


class TableOrderViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = models.TableOrder.objects.select_related("table", "customer").all()
    serializer_class = serializers.TableOrderSerializer

    @action(detail=False, methods=["post"])
    def place(self, request):
        table = None
        if request.data.get("table"):
            table = models.RestaurantTable.objects.filter(pk=request.data.get("table")).first()
        order = create_table_order(table=table, customer=request.user if request.user.is_authenticated else None, items=request.data.get("items") or [], notes=request.data.get("notes") or "")
        return Response(serializers.TableOrderSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        order = update_order_status(self.get_object(), request.data.get("status") or "preparing", actor=request.user, note=request.data.get("note") or "")
        return Response(serializers.TableOrderSerializer(order, context={"request": request}).data)


class KitchenQueueViewSet(viewsets.ModelViewSet):
    queryset = models.KitchenQueue.objects.select_related("order", "order__table", "assigned_to").all()
    serializer_class = serializers.KitchenQueueSerializer
    permission_classes = [permissions.IsAuthenticated]


class SuperDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.SuperDashboardSnapshot.objects.select_related("business_unit").all()
    serializer_class = serializers.SuperDashboardSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        business_unit = None
        if request.data.get("business_unit"):
            business_unit = models.BusinessUnit.objects.filter(pk=request.data.get("business_unit")).first()
        snapshot = build_super_dashboard_snapshot(business_unit=business_unit, period=request.data.get("period") or "today")
        return Response(serializers.SuperDashboardSnapshotSerializer(snapshot, context={"request": request}).data)


class ActivityAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ActivityAuditLog.objects.select_related("actor").all()
    serializer_class = serializers.ActivityAuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
