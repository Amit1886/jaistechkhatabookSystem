from django.urls import include, path
from rest_framework.routers import DefaultRouter

from subscription.views import PlanViewSet, SubscriptionViewSet

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="subscription-plans")
router.register("subscriptions", SubscriptionViewSet, basename="subscriptions")

urlpatterns = [path("", include(router.urls))]

