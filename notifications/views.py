from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from django.utils import timezone


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(getattr(user, "userprofile", None), "company", None)
        serializer.save(company=company, user=user)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"status": "ok"})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        obj = self.get_object()
        obj.mark_read()
        return Response(NotificationSerializer(obj, context={"request": request}).data)
