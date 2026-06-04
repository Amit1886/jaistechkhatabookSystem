from django.db import models
from rest_framework import permissions, viewsets

from fraud_detection.models import FraudSignal
from fraud_detection.serializers import FraudSignalSerializer


class FraudSignalViewSet(viewsets.ModelViewSet):
    queryset = FraudSignal.objects.select_related("user", "related_user").all()
    serializer_class = FraudSignalSerializer
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

