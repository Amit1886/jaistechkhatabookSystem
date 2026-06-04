from django.db import models
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from marketing.models import Campaign, CampaignMessage
from marketing.serializers import CampaignMessageSerializer, CampaignSerializer
from marketing.services import generate_ad_copy, start_campaign


class _CompanyScopedMixin:
    def _company(self):
        return getattr(getattr(self.request.user, "userprofile", None), "company", None)


class CampaignViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated]

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

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        campaign = self.get_object()
        start_campaign(campaign=campaign, actor=request.user)
        return Response(CampaignSerializer(campaign, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def generate_copy(self, request):
        objective = request.data.get("objective") or "promote"
        product = request.data.get("product") or "your product"
        language = request.data.get("language") or "en"
        return Response({"copy": generate_ad_copy(objective=objective, product=product, language=language)})


class CampaignMessageViewSet(_CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CampaignMessage.objects.select_related("campaign", "lead", "user").all()
    serializer_class = CampaignMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        company = self._company()
        return qs.filter(models.Q(campaign__company=company) | models.Q(campaign__company__isnull=True))

