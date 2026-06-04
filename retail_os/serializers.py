from rest_framework import serializers

from .models import (
    Branch,
    BranchAnalytics,
    BranchInventory,
    BranchPrice,
    BranchScreenMapping,
    BranchTransfer,
    BranchUser,
    CampaignPlaylist,
    CampaignPlaylistItem,
    ComboOffer,
    DarkStoreInventory,
    DeliveryAllocation,
    DeviceAssignment,
    DeviceEvent,
    DeviceHealth,
    DeviceLog,
    DynamicPriceLog,
    FestivalCampaign,
    IoTDevice,
    LiveAnnouncement,
    MediaAsset,
    OfferCampaign,
    PackingTask,
    PricingRule,
    QuickCommerceOrder,
    RetailAuditLog,
    RetailScreen,
    RiderProfile,
)


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"


class BranchUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchUser
        fields = "__all__"


class BranchInventorySerializer(serializers.ModelSerializer):
    sellable_qty = serializers.IntegerField(read_only=True)

    class Meta:
        model = BranchInventory
        fields = "__all__"


class BranchTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchTransfer
        fields = "__all__"


class BranchAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchAnalytics
        fields = "__all__"


class PricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = "__all__"
        read_only_fields = ("created_by",)


class OfferCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCampaign
        fields = "__all__"
        read_only_fields = ("created_by",)


class ComboOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComboOffer
        fields = "__all__"


class BranchPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchPrice
        fields = "__all__"
        read_only_fields = ("updated_by",)


class FestivalCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = FestivalCampaign
        fields = "__all__"


class DynamicPriceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicPriceLog
        fields = "__all__"
        read_only_fields = ("created_by",)


class RetailScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetailScreen
        fields = "__all__"


class MediaAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = "__all__"
        read_only_fields = ("created_by",)


class CampaignPlaylistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignPlaylistItem
        fields = "__all__"


class CampaignPlaylistSerializer(serializers.ModelSerializer):
    items = CampaignPlaylistItemSerializer(many=True, read_only=True)

    class Meta:
        model = CampaignPlaylist
        fields = "__all__"


class LiveAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveAnnouncement
        fields = "__all__"
        read_only_fields = ("created_by",)


class BranchScreenMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchScreenMapping
        fields = "__all__"


class IoTDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IoTDevice
        fields = "__all__"


class DeviceAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceAssignment
        fields = "__all__"


class DeviceHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceHealth
        fields = "__all__"


class DeviceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceLog
        fields = "__all__"


class DeviceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceEvent
        fields = "__all__"


class DarkStoreInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DarkStoreInventory
        fields = "__all__"


class QuickCommerceOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickCommerceOrder
        fields = "__all__"


class PackingTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackingTask
        fields = "__all__"


class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderProfile
        fields = "__all__"


class DeliveryAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAllocation
        fields = "__all__"


class RetailAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetailAuditLog
        fields = "__all__"

