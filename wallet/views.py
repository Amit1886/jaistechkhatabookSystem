from decimal import Decimal

from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from wallet.models import Wallet, WalletTransaction, WithdrawRequest
from wallet.serializers import WalletSerializer, WalletTransactionSerializer, WithdrawRequestSerializer
from wallet.services import approve_withdrawal, credit, debit, get_or_create_wallet, mark_withdrawal_paid, request_withdrawal


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Wallet.objects.all()
        return Wallet.objects.filter(user=user)

    @action(detail=False, methods=["post"])
    def credit(self, request):
        amount = Decimal(str(request.data.get("amount", "0")))
        source = request.data.get("source") or "manual"
        reference = request.data.get("reference") or ""
        credit(request.user, amount, source=source, reference=reference)
        wallet = get_or_create_wallet(request.user)
        return Response(WalletSerializer(wallet, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def debit(self, request):
        amount = Decimal(str(request.data.get("amount", "0")))
        source = request.data.get("source") or "manual"
        reference = request.data.get("reference") or ""
        try:
            debit(request.user, amount, source=source, reference=reference)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        wallet = get_or_create_wallet(request.user)
        return Response(WalletSerializer(wallet, context={"request": request}).data)


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = WalletTransaction.objects.select_related("wallet", "wallet__user")
        if user.is_superuser:
            return qs
        return qs.filter(wallet__user=user)


class WithdrawRequestViewSet(viewsets.ModelViewSet):
    serializer_class = WithdrawRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = WithdrawRequest.objects.select_related("wallet", "user")
        if user.is_superuser:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        amount = serializer.validated_data["amount"]
        try:
            wr = request_withdrawal(self.request.user, amount, metadata=serializer.validated_data.get("metadata"))
            serializer.instance = wr
        except ValueError as exc:
            raise serializers.ValidationError({"amount": str(exc)})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        obj = self.get_object()
        approve_withdrawal(obj, approver=request.user, payout_reference=request.data.get("payout_reference", ""))
        return Response(WithdrawRequestSerializer(obj, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def mark_paid(self, request, pk=None):
        obj = self.get_object()
        mark_withdrawal_paid(obj, payout_reference=request.data.get("payout_reference", ""))
        return Response(WithdrawRequestSerializer(obj, context={"request": request}).data)
