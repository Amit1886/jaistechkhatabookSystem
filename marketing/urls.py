from django.urls import include, path
from rest_framework.routers import DefaultRouter

from marketing.views import CampaignMessageViewSet, CampaignViewSet

router = DefaultRouter()
router.register("campaigns", CampaignViewSet, basename="marketing-campaigns")
router.register("campaign-messages", CampaignMessageViewSet, basename="marketing-campaign-messages")

urlpatterns = [path("", include(router.urls))]

