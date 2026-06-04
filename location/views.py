from django.db import models
from rest_framework import permissions, viewsets

from .models import Country, District, Pincode, State
from .serializers import CountrySerializer, DistrictSerializer, PincodeSerializer, StateSerializer


class _TenantScopedQuerysetMixin:
    """
    Minimal, backward-compatible tenant scoping.

    If the authenticated user has `user.userprofile.company`, restrict data to:
    - that company or global master rows (company is null).
    Superusers can see all rows.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return qs.none()
        if getattr(user, "is_superuser", False):
            return qs
        company = getattr(getattr(user, "userprofile", None), "company", None)
        if not company:
            return qs.filter(company__isnull=True)
        return qs.filter(models.Q(company=company) | models.Q(company__isnull=True))


class CountryViewSet(_TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "is_superuser", False):
            serializer.save()
            return
        company = getattr(getattr(user, "userprofile", None), "company", None)
        serializer.save(company=company)


class StateViewSet(_TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = State.objects.select_related("country")
    serializer_class = StateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "is_superuser", False):
            serializer.save()
            return
        company = getattr(getattr(user, "userprofile", None), "company", None)
        serializer.save(company=company)


class DistrictViewSet(_TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = District.objects.select_related("state", "state__country")
    serializer_class = DistrictSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "is_superuser", False):
            serializer.save()
            return
        company = getattr(getattr(user, "userprofile", None), "company", None)
        serializer.save(company=company)


class PincodeViewSet(_TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Pincode.objects.select_related("district", "district__state", "district__state__country")
    serializer_class = PincodeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "is_superuser", False):
            serializer.save()
            return
        company = getattr(getattr(user, "userprofile", None), "company", None)
        serializer.save(company=company)
