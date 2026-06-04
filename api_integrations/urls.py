from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api_integrations.views import IntegrationConnectionViewSet

router = DefaultRouter()
router.register("connections", IntegrationConnectionViewSet, basename="integration-connections")

urlpatterns = [path("", include(router.urls))]

