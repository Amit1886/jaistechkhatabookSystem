from django.db import models
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AgentCustomerAssignment
from .serializers import AgentCustomerAssignmentSerializer
from .services import assign_customer_to_agent


class AgentCustomerAssignmentViewSet(viewsets.ModelViewSet):
    queryset = AgentCustomerAssignment.objects.select_related("customer", "agent", "assigned_by").all()
    serializer_class = AgentCustomerAssignmentSerializer
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
            return qs.filter(agent=user, unassigned_at__isnull=True)
        if role == "customer":
            return qs.filter(customer=user, unassigned_at__isnull=True)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        company = self._company()
        assignment = assign_customer_to_agent(
            company=company,
            customer=serializer.validated_data["customer"],
            agent=serializer.validated_data["agent"],
            assigned_by=user,
            reason=serializer.validated_data.get("reason") or "",
            metadata=serializer.validated_data.get("metadata") or {},
        )
        serializer.instance = assignment

    @action(detail=False, methods=["get"])
    def my_agent(self, request):
        company = self._company()
        assignment = (
            AgentCustomerAssignment.objects.filter(company=company, customer=request.user, unassigned_at__isnull=True)
            .select_related("agent")
            .order_by("-assigned_at", "-id")
            .first()
        )
        if not assignment:
            return Response({"agent": None})
        return Response({"agent": assignment.agent_id})

