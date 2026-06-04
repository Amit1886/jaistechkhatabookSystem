from django.urls import include, path
from rest_framework.routers import DefaultRouter

from performance.views import LeaderboardViewSet, RewardViewSet, TargetViewSet

router = DefaultRouter()
router.register("targets", TargetViewSet, basename="performance-targets")
router.register("leaderboard", LeaderboardViewSet, basename="performance-leaderboard")
router.register("rewards", RewardViewSet, basename="performance-rewards")

urlpatterns = [path("", include(router.urls))]

