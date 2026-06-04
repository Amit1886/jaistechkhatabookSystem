from django.db import models
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Lead, LeadActivity
from .serializers import LeadActivitySerializer, LeadSerializer
from .services import assign_lead, auto_assign_lead


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _company(self):
        return getattr(getattr(self.request.user, "userprofile", None), "company", None)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        company = self._company()
        qs = qs.filter(models.Q(company=company) | models.Q(company__isnull=True))
        role = (getattr(user, "role", "") or "").strip().lower()
        if role in {"agent", "super_agent"}:
            return qs.filter(assigned_to=user)
        if role == "customer":
            return qs.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        company = self._company()
        lead = serializer.save(company=company, created_by=user)
        auto_assign_lead(lead=lead)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        lead = self.get_object()
        assigned_to_id = request.data.get("assigned_to")
        if not assigned_to_id:
            return Response({"detail": "assigned_to is required"}, status=400)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assignee = User.objects.filter(id=assigned_to_id).first()
        if not assignee:
            return Response({"detail": "assignee not found"}, status=404)
        assign_lead(lead, assigned_to=assignee, actor=request.user, reason=str(request.data.get("reason") or ""))
        return Response(LeadSerializer(lead, context={"request": request}).data)


class LeadActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeadActivity.objects.select_related("lead", "actor").all()
    serializer_class = LeadActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def _company(self):
        return getattr(getattr(self.request.user, "userprofile", None), "company", None)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        company = self._company()
        return qs.filter(models.Q(lead__company=company) | models.Q(lead__company__isnull=True))

