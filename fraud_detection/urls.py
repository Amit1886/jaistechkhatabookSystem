from django.urls import include, path
from rest_framework.routers import DefaultRouter

from fraud_detection.views import FraudSignalViewSet

router = DefaultRouter()
router.register("signals", FraudSignalViewSet, basename="fraud-signals")

urlpatterns = [path("", include(router.urls))]

