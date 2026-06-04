from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.utils import OperationalError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import Product
from khataapp.models import Party
from procurement.models import SupplierPriceHistory, SupplierProduct, SupplierRating
from procurement.serializers import (
    SupplierPriceHistorySerializer,
    SupplierProductSerializer,
    SupplierRatingSerializer,
    SupplierSerializer,
)
from procurement.services import best_supplier_for_product, rank_suppliers_for_product, supplier_ratings_map


def _missing_tables_response():
    return Response(
        {"detail": "Procurement module tables missing. Run migrations: manage.py migrate procurement"},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class SuppliersListCreateAPI(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierSerializer

    def get_queryset(self):
        qs = Party.objects.filter(party_type="supplier")
        if self.request.user.is_staff or self.request.user.is_superuser:
            owner_id = (self.request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(owner_id=int(owner_id))
                except Exception:
                    pass
            return qs.order_by("name", "id")
        return qs.filter(owner=self.request.user).order_by("name", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        suppliers = list(self.get_queryset().only("id", "owner_id"))
        ids = [int(s.id) for s in suppliers]
        if not ids:
            ctx["rating_map"] = {}
            return ctx

        rating_owner = self.request.user
        if self.request.user.is_staff or self.request.user.is_superuser:
            owner_id = (self.request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    rating_owner = int(owner_id)
                except Exception:
                    rating_owner = self.request.user
            else:
                # Multi-tenant list without a fixed owner: skip ratings to avoid mixing tenants.
                ctx["rating_map"] = {}
                return ctx

        ctx["rating_map"] = supplier_ratings_map(rating_owner, ids)
        return ctx

    def perform_create(self, serializer):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            serializer.save(owner=self.request.user, party_type="supplier")
            return

        # Staff/admin can create suppliers for a specific owner (tenant).
        owner_id = (self.request.data.get("owner_id") or "").strip()
        if owner_id:
            try:
                serializer.save(owner_id=int(owner_id), party_type="supplier")
                return
            except Exception:
                pass
        serializer.save(owner=self.request.user, party_type="supplier")


class SupplierRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierSerializer
    queryset = Party.objects.filter(party_type="supplier")

    def get_object(self):
        obj = super().get_object()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return obj
        if obj.owner_id != self.request.user.id:
            raise permissions.PermissionDenied("Not allowed.")
        return obj


class SupplierProductListCreateAPI(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierProductSerializer

    def get_queryset(self):
        try:
            qs = SupplierProduct.objects.select_related("supplier", "product").all()
        except OperationalError:
            return SupplierProduct.objects.none()
        if self.request.user.is_staff or self.request.user.is_superuser:
            owner_id = (self.request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(owner_id=int(owner_id))
                except Exception:
                    pass
            return qs.order_by("-last_updated", "-id")
        return qs.filter(owner=self.request.user).order_by("-last_updated", "-id")

    @transaction.atomic
    def perform_create(self, serializer):
        owner = self.request.user
        supplier_id = serializer.validated_data.get("supplier").id
        product_id = serializer.validated_data.get("product").id

        supplier = get_object_or_404(Party, id=supplier_id, party_type="supplier")
        product = get_object_or_404(Product, id=product_id)

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            if supplier.owner_id != owner.id or product.owner_id != owner.id:
                raise permissions.PermissionDenied("Supplier/Product not in your account.")
        else:
            # Staff: honor owner_id if present; else default to current user.
            owner_id_raw = (self.request.data.get("owner") or self.request.data.get("owner_id") or "").strip()
            if owner_id_raw:
                try:
                    owner = type(self.request.user).objects.get(id=int(owner_id_raw))
                except Exception:
                    owner = self.request.user

        serializer.save(owner=owner)


class SupplierProductRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierProductSerializer
    queryset = SupplierProduct.objects.select_related("supplier", "product")

    def get_object(self):
        obj = super().get_object()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return obj
        if obj.owner_id != self.request.user.id:
            raise permissions.PermissionDenied("Not allowed.")
        return obj

    @transaction.atomic
    def perform_update(self, serializer):
        obj = self.get_object()
        if not (self.request.user.is_staff or self.request.user.is_superuser) and obj.owner_id != self.request.user.id:
            raise permissions.PermissionDenied("Not allowed.")
        serializer.instance._updated_by = self.request.user
        serializer.save()


class BestSupplierAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id: int):
        product = get_object_or_404(Product, id=product_id)
        if not (request.user.is_staff or request.user.is_superuser) and product.owner_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        # Optional weights (query params)
        def _d(key, default):
            raw = (request.query_params.get(key) or "").strip()
            try:
                return Decimal(raw)
            except Exception:
                return default

        pw = _d("price_weight", None)
        dw = _d("delivery_weight", None)
        rw = _d("rating_weight", None)

        try:
            ranked = rank_suppliers_for_product(
                owner=product.owner,
                product_id=product.id,
                price_weight=pw,
                delivery_weight=dw,
                rating_weight=rw,
            )
            best = best_supplier_for_product(
                owner=product.owner,
                product_id=product.id,
                price_weight=pw,
                delivery_weight=dw,
                rating_weight=rw,
            )
        except OperationalError:
            return _missing_tables_response()

        data = {
            "product": {"id": product.id, "name": product.name, "sku": product.sku},
            "best": (best.__dict__ if best else None),
            "options": [o.__dict__ for o in ranked],
        }
        return Response(data)


class SupplierPriceHistoryListAPI(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierPriceHistorySerializer
    pagination_class = None

    def get_queryset(self):
        try:
            qs = SupplierPriceHistory.objects.select_related("supplier", "product").all()
        except OperationalError:
            return SupplierPriceHistory.objects.none()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            qs = qs.filter(owner=self.request.user)
        else:
            owner_id = (self.request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    qs = qs.filter(owner_id=int(owner_id))
                except Exception:
                    pass

        product_id = (self.request.query_params.get("product_id") or "").strip()
        supplier_id = (self.request.query_params.get("supplier_id") or "").strip()
        if product_id:
            try:
                qs = qs.filter(product_id=int(product_id))
            except Exception:
                pass
        if supplier_id:
            try:
                qs = qs.filter(supplier_id=int(supplier_id))
            except Exception:
                pass
        return qs.order_by("-updated_at", "-id")[:500]


class SupplierRatingUpsertAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            SupplierRating.objects.none().exists()
        except OperationalError:
            return _missing_tables_response()

        supplier_id_raw = (request.data.get("supplier_id") or "").strip()
        try:
            supplier_id = int(supplier_id_raw)
        except Exception:
            return Response({"detail": "Invalid supplier_id"}, status=status.HTTP_400_BAD_REQUEST)

        supplier = get_object_or_404(Party, id=supplier_id, party_type="supplier", owner=request.user)

        payload = {
            "delivery_speed": request.data.get("delivery_speed", 3),
            "product_quality": request.data.get("product_quality", 3),
            "pricing": request.data.get("pricing", 3),
            "comment": request.data.get("comment", ""),
        }

        obj, _ = SupplierRating.objects.update_or_create(
            owner=request.user,
            supplier=supplier,
            rated_by=request.user,
            defaults=payload,
        )
        return Response(SupplierRatingSerializer(obj).data)
