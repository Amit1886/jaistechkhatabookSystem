from rest_framework import permissions, viewsets

from performance.models import LeaderboardEntry, Reward, Target
from performance.serializers import LeaderboardEntrySerializer, RewardSerializer, TargetSerializer


class TargetViewSet(viewsets.ModelViewSet):
    queryset = Target.objects.select_related("user")
    serializer_class = TargetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaderboardEntry.objects.select_related("user")
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [permissions.IsAuthenticated]


class RewardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Reward.objects.select_related("user")
    serializer_class = RewardSerializer
    permission_classes = [permissions.IsAuthenticated]

