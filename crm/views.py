from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from crm.models import CallLog, CustomerNote, CustomerProfile, FollowUp
from crm.serializers import CallLogSerializer, CustomerNoteSerializer, CustomerProfileSerializer, FollowUpSerializer


class _CompanyScopedMixin:
    def _company(self):
        return getattr(getattr(self.request.user, "userprofile", None), "company", None)

    def scope_queryset(self, qs):
        user = self.request.user
        if user.is_superuser:
            return qs
        company = self._company()
        return qs.filter(company=company) if qs.model is CustomerProfile else qs.filter(customer__company=company)


class CustomerProfileViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def perform_create(self, serializer):
        company = self._company()
        serializer.save(company=company)


class CustomerNoteViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = CustomerNote.objects.select_related("customer", "author")
    serializer_class = CustomerNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class CallLogViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = CallLog.objects.select_related("customer", "agent")
    serializer_class = CallLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)


class FollowUpViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = FollowUp.objects.select_related("customer", "owner")
    serializer_class = FollowUpSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        obj = self.get_object()
        obj.mark_done()
        return Response(FollowUpSerializer(obj, context={"request": request}).data)

