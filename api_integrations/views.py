from django.db import models
from rest_framework import permissions, viewsets

from api_integrations.models import IntegrationConnection
from api_integrations.serializers import IntegrationConnectionSerializer


class IntegrationConnectionViewSet(viewsets.ModelViewSet):
    queryset = IntegrationConnection.objects.all()
    serializer_class = IntegrationConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _company(self):
        return getattr(getattr(self.request.user, "userprofile", None), "company", None)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        company = self._company()
        return qs.filter(models.Q(company=company) | models.Q(company__isnull=True))

    def perform_create(self, serializer):
        user = self.request.user
        company = self._company()
        serializer.save(company=company, created_by=user)

