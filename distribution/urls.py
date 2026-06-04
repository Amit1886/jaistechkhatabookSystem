from django.urls import include, path
from rest_framework.routers import DefaultRouter

from distribution import views

router = DefaultRouter()
router.register("industries", views.IndustryViewSet, basename="distribution-industries")
router.register("platforms", views.AppPlatformViewSet, basename="distribution-platforms")
router.register("features", views.FeatureRegistryViewSet, basename="distribution-features")
router.register("modules", views.ModuleRegistryViewSet, basename="distribution-modules")
router.register("builds", views.SoftwareBuildViewSet, basename="distribution-builds")
router.register("remote-configs", views.RemoteConfigViewSet, basename="distribution-remote-configs")
router.register("devices", views.DeviceRegistryViewSet, basename="distribution-devices")
router.register("sync", views.DistributionSyncViewSet, basename="distribution-sync")

urlpatterns = [
    path("", include(router.urls)),
]

