from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from billing.models import Subscription
from billing.services import ensure_free_plan, upgrade_subscription
from subscription.serializers import PlanSerializer, SubscriptionSerializer


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Subscription._meta.get_field("plan").related_model.objects.filter(active=True).order_by("price_monthly", "price_yearly")
    )
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("plan", "user")
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(user=user)

    def perform_create(self, serializer):
        plan = serializer.validated_data["plan"]
        upgrade_subscription(self.request.user, plan)
        serializer.instance = Subscription.objects.filter(user=self.request.user).order_by("-created_at").first()

    @action(detail=False, methods=["post"])
    def free(self, request):
        sub = ensure_free_plan(request.user)
        return Response(SubscriptionSerializer(sub, context={"request": request}).data, status=status.HTTP_200_OK)

