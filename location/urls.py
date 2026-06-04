from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CountryViewSet, DistrictViewSet, PincodeViewSet, StateViewSet

router = DefaultRouter()
router.register("countries", CountryViewSet, basename="location-country")
router.register("states", StateViewSet, basename="location-state")
router.register("districts", DistrictViewSet, basename="location-district")
router.register("pincodes", PincodeViewSet, basename="location-pincode")

urlpatterns = [path("", include(router.urls))]
