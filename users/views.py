from rest_framework import filters, permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.db import transaction
from vendors.models import Vendor

from .models import CommissionLedger, UserProfileExt, WalletLedger
from .serializers import CommissionLedgerSerializer, SubUserSerializer, UserProfileExtSerializer, WalletLedgerSerializer
from saas.utils.permissions import user_has_permission

User = get_user_model()


class UserProfileExtViewSet(viewsets.ModelViewSet):
    queryset = UserProfileExt.objects.select_related("user").all()
    serializer_class = UserProfileExtSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__email", "user__username", "role"]
    ordering_fields = ["created_at", "updated_at", "role"]


class WalletLedgerViewSet(viewsets.ModelViewSet):
    queryset = WalletLedger.objects.select_related("user").all()
    serializer_class = WalletLedgerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["reference", "source", "user__email"]
    ordering_fields = ["created_at", "amount"]


class CommissionLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CommissionLedger.objects.select_related("user").all()
    serializer_class = CommissionLedgerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["order_id", "role", "user__email"]
    ordering_fields = ["created_at", "commission_amount", "margin"]


class SubUserViewSet(viewsets.ModelViewSet):
    """
    Owner -> Sub-user management (Phase A, backend-only).

    Route: /api/v1/users/subusers/
    """

    serializer_class = SubUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show sub-users belonging to the current owner.
        return User.objects.filter(parent=self.request.user).order_by("-id")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not user_has_permission(request.user, "subuser_create") and (request.user.primary_role or "").lower() != "owner":
            raise PermissionDenied("Missing permission: subuser_create")

        email = (request.data.get("email") or "").strip().lower()
        mobile = (request.data.get("mobile") or "").strip()
        username = (request.data.get("username") or "").strip() or (email.split("@")[0] if email else "")
        password = (request.data.get("password") or "").strip() or User.objects.make_random_password()
        store_type = (request.data.get("store_type") or "hybrid").strip().lower()
        primary_role = (request.data.get("primary_role") or "staff").strip().lower()
        permissions_json = request.data.get("permissions_json") or {}
        if not isinstance(permissions_json, dict):
            permissions_json = {}

        if not email:
            raise PermissionDenied("email is required")

        # In Phase A, subusers belong to the owner's vendor (if any).
        seller = getattr(request.user, "seller", None)
        if not seller:
            try:
                sub = (getattr(request, "vendor_subdomain", "") or "").strip().lower()
                if sub:
                    seller = Vendor.objects.filter(subdomain=sub, is_active=True).first()
            except Exception:
                seller = None

        user = User.objects.create_user(
            username=username[:150] or None,
            email=email,
            mobile=mobile or None,
            password=password,
        )
        user.parent = request.user
        user.store_type = store_type if store_type in {"b2b", "b2c", "hybrid"} else "hybrid"
        user.primary_role = primary_role
        user.permissions_json = permissions_json
        user.seller = seller
        user.save(update_fields=["parent", "store_type", "primary_role", "permissions_json", "seller"])

        ser = self.get_serializer(user)
        return Response(ser.data, status=201)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.parent_id != request.user.id:
            raise PermissionDenied("Not allowed")
        if not user_has_permission(request.user, "subuser_update") and (request.user.primary_role or "").lower() != "owner":
            raise PermissionDenied("Missing permission: subuser_update")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        if obj.parent_id != request.user.id:
            raise PermissionDenied("Not allowed")
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return Response({"ok": True, "status": "deactivated"})
