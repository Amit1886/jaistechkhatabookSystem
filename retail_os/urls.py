from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BranchAnalyticsViewSet,
    BranchInventoryViewSet,
    BranchPriceViewSet,
    BranchScreenMappingViewSet,
    BranchTransferViewSet,
    BranchUserViewSet,
    BranchViewSet,
    CampaignPlaylistItemViewSet,
    CampaignPlaylistViewSet,
    ComboOfferViewSet,
    DarkStoreInventoryViewSet,
    DeliveryAllocationViewSet,
    DeviceAssignmentViewSet,
    DeviceEventViewSet,
    DeviceHealthViewSet,
    DeviceLogViewSet,
    DynamicPriceLogViewSet,
    FestivalCampaignViewSet,
    IoTDeviceViewSet,
    LiveAnnouncementViewSet,
    MediaAssetViewSet,
    OfferCampaignViewSet,
    PackingTaskViewSet,
    PricingRuleViewSet,
    QuickCommerceOrderViewSet,
    RetailAuditLogViewSet,
    RetailScreenViewSet,
    RiderProfileViewSet,
)

router = DefaultRouter()
router.register("branches", BranchViewSet)
router.register("branch-users", BranchUserViewSet)
router.register("branch-inventory", BranchInventoryViewSet)
router.register("branch-transfers", BranchTransferViewSet)
router.register("branch-analytics", BranchAnalyticsViewSet)
router.register("pricing-rules", PricingRuleViewSet)
router.register("offer-campaigns", OfferCampaignViewSet)
router.register("combo-offers", ComboOfferViewSet)
router.register("branch-prices", BranchPriceViewSet)
router.register("festival-campaigns", FestivalCampaignViewSet)
router.register("dynamic-price-logs", DynamicPriceLogViewSet)
router.register("retail-screens", RetailScreenViewSet)
router.register("media-assets", MediaAssetViewSet)
router.register("campaign-playlists", CampaignPlaylistViewSet)
router.register("campaign-playlist-items", CampaignPlaylistItemViewSet)
router.register("live-announcements", LiveAnnouncementViewSet)
router.register("branch-screen-mappings", BranchScreenMappingViewSet)
router.register("iot-devices", IoTDeviceViewSet)
router.register("device-assignments", DeviceAssignmentViewSet)
router.register("device-health", DeviceHealthViewSet)
router.register("device-logs", DeviceLogViewSet)
router.register("device-events", DeviceEventViewSet)
router.register("dark-store-inventory", DarkStoreInventoryViewSet)
router.register("quick-orders", QuickCommerceOrderViewSet)
router.register("packing-tasks", PackingTaskViewSet)
router.register("riders", RiderProfileViewSet)
router.register("delivery-allocations", DeliveryAllocationViewSet)
router.register("audit-logs", RetailAuditLogViewSet)

urlpatterns = [path("", include(router.urls))]
