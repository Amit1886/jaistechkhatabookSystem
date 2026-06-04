from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import decorators, filters, permissions, response, status, viewsets

from products.models import Product

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
from .serializers import (
    BranchAnalyticsSerializer,
    BranchInventorySerializer,
    BranchPriceSerializer,
    BranchScreenMappingSerializer,
    BranchSerializer,
    BranchTransferSerializer,
    BranchUserSerializer,
    CampaignPlaylistItemSerializer,
    CampaignPlaylistSerializer,
    ComboOfferSerializer,
    DarkStoreInventorySerializer,
    DeliveryAllocationSerializer,
    DeviceAssignmentSerializer,
    DeviceEventSerializer,
    DeviceHealthSerializer,
    DeviceLogSerializer,
    DynamicPriceLogSerializer,
    FestivalCampaignSerializer,
    IoTDeviceSerializer,
    LiveAnnouncementSerializer,
    MediaAssetSerializer,
    OfferCampaignSerializer,
    PackingTaskSerializer,
    PricingRuleSerializer,
    QuickCommerceOrderSerializer,
    RetailAuditLogSerializer,
    RetailScreenSerializer,
    RiderProfileSerializer,
)
from .services.iot import record_device_health, register_device_event
from .services.pricing import calculate_dynamic_price, pricing_analytics, recalculate_branch_prices
from .services.quick_commerce import allocate_nearest_rider, create_packing_tasks, mark_order_packed
from .services.realtime import publish_retail_event


class RetailModelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-id"]


class BranchViewSet(RetailModelViewSet):
    queryset = Branch.objects.select_related("warehouse", "manager").all()
    serializer_class = BranchSerializer
    search_fields = ["name", "code", "city", "state"]
    ordering_fields = ["name", "created_at"]

    @decorators.action(detail=False, methods=["get"])
    def command_center(self, request):
        today = timezone.localdate()
        analytics = BranchAnalytics.objects.filter(snapshot_date=today)
        payload = {
            "branch_count": Branch.objects.filter(is_active=True).count(),
            "locked_branches": Branch.objects.filter(is_locked=True).count(),
            "emergency_branches": Branch.objects.filter(emergency_mode=True).count(),
            "live_sales_total": analytics.aggregate(total=Sum("sales_total"))["total"] or 0,
            "live_order_count": analytics.aggregate(total=Sum("order_count"))["total"] or 0,
            "branch_ranking": list(
                analytics.select_related("branch")
                .values("branch_id", "branch__name", "branch__code")
                .annotate(sales=Sum("sales_total"), margin=Sum("gross_margin"), orders=Sum("order_count"))
                .order_by("-sales")[:20]
            ),
            "stock_alerts": BranchInventory.objects.filter(available_qty__lte=0).count(),
        }
        return response.Response(payload)

    @decorators.action(detail=True, methods=["post"], url_path="lock")
    def lock_branch(self, request, pk=None):
        branch = self.get_object()
        branch.is_locked = True
        branch.save(update_fields=["is_locked", "updated_at"])
        publish_retail_event("branches", "branch.locked", {"branch_id": branch.id})
        return response.Response({"status": "locked"})

    @decorators.action(detail=True, methods=["post"], url_path="unlock")
    def unlock_branch(self, request, pk=None):
        branch = self.get_object()
        branch.is_locked = False
        branch.save(update_fields=["is_locked", "updated_at"])
        publish_retail_event("branches", "branch.unlocked", {"branch_id": branch.id})
        return response.Response({"status": "unlocked"})

    @decorators.action(detail=True, methods=["post"], url_path="emergency")
    def emergency(self, request, pk=None):
        branch = self.get_object()
        branch.emergency_mode = bool(request.data.get("enabled", True))
        branch.save(update_fields=["emergency_mode", "updated_at"])
        publish_retail_event("branches", "branch.emergency", {"branch_id": branch.id, "enabled": branch.emergency_mode})
        return response.Response({"enabled": branch.emergency_mode})


class BranchUserViewSet(RetailModelViewSet):
    queryset = BranchUser.objects.select_related("branch", "user").all()
    serializer_class = BranchUserSerializer
    search_fields = ["branch__name", "user__email", "role"]


class BranchInventoryViewSet(RetailModelViewSet):
    queryset = BranchInventory.objects.select_related("branch", "product").all()
    serializer_class = BranchInventorySerializer
    search_fields = ["branch__name", "product__name", "product__sku", "product__barcode"]
    ordering_fields = ["available_qty", "reserved_qty", "updated_at", "expiry_date"]


class BranchTransferViewSet(RetailModelViewSet):
    queryset = BranchTransfer.objects.select_related("source_branch", "destination_branch", "product").all()
    serializer_class = BranchTransferSerializer
    search_fields = ["transfer_no", "source_branch__name", "destination_branch__name", "product__name"]


class BranchAnalyticsViewSet(RetailModelViewSet):
    queryset = BranchAnalytics.objects.select_related("branch").all()
    serializer_class = BranchAnalyticsSerializer


class PricingRuleViewSet(RetailModelViewSet):
    queryset = PricingRule.objects.select_related("branch", "product", "category").all()
    serializer_class = PricingRuleSerializer
    search_fields = ["name", "condition_type", "offer_tag"]
    ordering_fields = ["priority", "starts_at", "ends_at", "updated_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request):
        product = Product.objects.get(pk=request.data["product_id"])
        branch = Branch.objects.filter(pk=request.data.get("branch_id")).first() if request.data.get("branch_id") else None
        payload = calculate_dynamic_price(
            product,
            branch=branch,
            quantity=int(request.data.get("quantity", 1)),
            customer_segment=request.data.get("customer_segment", ""),
            channel=request.data.get("channel", "pos"),
        )
        return response.Response(payload)

    @decorators.action(detail=False, methods=["post"], url_path="recalculate")
    def recalculate(self, request):
        branch = Branch.objects.filter(pk=request.data.get("branch_id")).first() if request.data.get("branch_id") else None
        logs = recalculate_branch_prices(branch=branch, product_ids=request.data.get("product_ids"), actor=request.user)
        return response.Response({"updated": len(logs)})

    @decorators.action(detail=False, methods=["get"], url_path="analytics")
    def analytics(self, request):
        return response.Response(pricing_analytics(days=int(request.query_params.get("days", 30))))


class OfferCampaignViewSet(RetailModelViewSet):
    queryset = OfferCampaign.objects.prefetch_related("branches", "products", "categories").all()
    serializer_class = OfferCampaignSerializer
    search_fields = ["name", "badge_text", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=["post"], url_path="push-live")
    def push_live(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = OfferCampaign.Status.LIVE
        campaign.save(update_fields=["status", "updated_at"])
        publish_retail_event("pricing", "campaign.live", {"campaign_id": campaign.id, "name": campaign.name})
        publish_retail_event("signage", "campaign.live", {"campaign_id": campaign.id, "name": campaign.name})
        return response.Response({"status": campaign.status})


class ComboOfferViewSet(RetailModelViewSet):
    queryset = ComboOffer.objects.prefetch_related("products").select_related("branch").all()
    serializer_class = ComboOfferSerializer


class BranchPriceViewSet(RetailModelViewSet):
    queryset = BranchPrice.objects.select_related("branch", "product").all()
    serializer_class = BranchPriceSerializer
    search_fields = ["branch__name", "product__name", "offer_tag"]

    def perform_create(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        publish_retail_event("pricing", "branch_price.updated", {"branch_id": instance.branch_id, "product_id": instance.product_id})

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        publish_retail_event("pricing", "branch_price.updated", {"branch_id": instance.branch_id, "product_id": instance.product_id})


class FestivalCampaignViewSet(RetailModelViewSet):
    queryset = FestivalCampaign.objects.select_related("offer_campaign").all()
    serializer_class = FestivalCampaignSerializer


class DynamicPriceLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DynamicPriceLog.objects.select_related("rule", "campaign", "branch", "product").all()
    serializer_class = DynamicPriceLogSerializer
    permission_classes = [permissions.IsAuthenticated]


class RetailScreenViewSet(RetailModelViewSet):
    queryset = RetailScreen.objects.select_related("branch").all()
    serializer_class = RetailScreenSerializer
    search_fields = ["name", "device_uid", "branch__name"]

    @decorators.action(detail=True, methods=["post"], url_path="heartbeat")
    def heartbeat(self, request, pk=None):
        screen = self.get_object()
        screen.is_online = True
        screen.last_seen_at = timezone.now()
        screen.save(update_fields=["is_online", "last_seen_at"])
        return response.Response({"status": "online"})

    @decorators.action(detail=True, methods=["get"], url_path="player-state")
    def player_state(self, request, pk=None):
        screen = self.get_object()
        now = timezone.now()
        playlists = CampaignPlaylist.objects.filter(is_active=True).filter(screens=screen, starts_at__lte=now, ends_at__gte=now).distinct()
        if not playlists.exists() and screen.branch_id:
            playlists = CampaignPlaylist.objects.filter(is_active=True, branches=screen.branch, starts_at__lte=now, ends_at__gte=now).distinct()
        announcements = LiveAnnouncement.objects.filter(starts_at__lte=now).filter(ends_at__isnull=True) | LiveAnnouncement.objects.filter(
            starts_at__lte=now, ends_at__gte=now
        )
        return response.Response(
            {
                "screen": RetailScreenSerializer(screen).data,
                "playlists": CampaignPlaylistSerializer(playlists.order_by("priority")[:5], many=True).data,
                "announcements": LiveAnnouncementSerializer(announcements.distinct()[:10], many=True).data,
            }
        )


class MediaAssetViewSet(RetailModelViewSet):
    queryset = MediaAsset.objects.all()
    serializer_class = MediaAssetSerializer
    search_fields = ["title", "media_type"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CampaignPlaylistViewSet(RetailModelViewSet):
    queryset = CampaignPlaylist.objects.prefetch_related("screens", "branches", "items__asset").all()
    serializer_class = CampaignPlaylistSerializer


class CampaignPlaylistItemViewSet(RetailModelViewSet):
    queryset = CampaignPlaylistItem.objects.select_related("playlist", "asset").all()
    serializer_class = CampaignPlaylistItemSerializer


class LiveAnnouncementViewSet(RetailModelViewSet):
    queryset = LiveAnnouncement.objects.prefetch_related("branches", "screens").all()
    serializer_class = LiveAnnouncementSerializer
    search_fields = ["title", "message", "severity"]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        publish_retail_event("signage", "announcement.created", {"announcement_id": instance.id, "fullscreen": instance.fullscreen})


class BranchScreenMappingViewSet(RetailModelViewSet):
    queryset = BranchScreenMapping.objects.select_related("branch", "screen").all()
    serializer_class = BranchScreenMappingSerializer


class IoTDeviceViewSet(RetailModelViewSet):
    queryset = IoTDevice.objects.select_related("branch").all()
    serializer_class = IoTDeviceSerializer
    search_fields = ["name", "device_uid", "device_type", "branch__name"]

    @decorators.action(detail=True, methods=["post"], url_path="event")
    def event(self, request, pk=None):
        device = self.get_object()
        event = register_device_event(device, request.data.get("event_type", "heartbeat"), request.data.get("payload", {}))
        return response.Response(DeviceEventSerializer(event).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="health")
    def health(self, request, pk=None):
        device = self.get_object()
        health = record_device_health(
            device,
            status=request.data.get("status", "online"),
            metrics=request.data.get("metrics", {}),
            battery_percent=request.data.get("battery_percent"),
            signal_strength=request.data.get("signal_strength"),
            error_message=request.data.get("error_message", ""),
        )
        return response.Response(DeviceHealthSerializer(health).data)


class DeviceAssignmentViewSet(RetailModelViewSet):
    queryset = DeviceAssignment.objects.select_related("device", "branch", "terminal").all()
    serializer_class = DeviceAssignmentSerializer


class DeviceHealthViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceHealth.objects.select_related("device").all()
    serializer_class = DeviceHealthSerializer
    permission_classes = [permissions.IsAuthenticated]


class DeviceLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceLog.objects.select_related("device").all()
    serializer_class = DeviceLogSerializer
    permission_classes = [permissions.IsAuthenticated]


class DeviceEventViewSet(RetailModelViewSet):
    queryset = DeviceEvent.objects.select_related("device", "branch", "product").all()
    serializer_class = DeviceEventSerializer


class DarkStoreInventoryViewSet(RetailModelViewSet):
    queryset = DarkStoreInventory.objects.select_related("branch", "product").all()
    serializer_class = DarkStoreInventorySerializer
    search_fields = ["branch__name", "product__name", "pick_zone", "bin_code"]


class QuickCommerceOrderViewSet(RetailModelViewSet):
    queryset = QuickCommerceOrder.objects.select_related("order", "branch").all()
    serializer_class = QuickCommerceOrderSerializer
    search_fields = ["order__order_number", "branch__name", "status"]

    @decorators.action(detail=True, methods=["post"], url_path="create-packing-tasks")
    def create_tasks(self, request, pk=None):
        tasks = create_packing_tasks(self.get_object())
        return response.Response({"created": len(tasks)})

    @decorators.action(detail=True, methods=["post"], url_path="allocate-rider")
    def allocate_rider(self, request, pk=None):
        allocation = allocate_nearest_rider(self.get_object())
        return response.Response(DeliveryAllocationSerializer(allocation).data)

    @decorators.action(detail=True, methods=["post"], url_path="mark-packed")
    def mark_packed(self, request, pk=None):
        quick_order = mark_order_packed(self.get_object())
        return response.Response(QuickCommerceOrderSerializer(quick_order).data)

    @decorators.action(detail=False, methods=["get"], url_path="analytics")
    def analytics(self, request):
        qs = QuickCommerceOrder.objects.all()
        return response.Response(
            {
                "active_orders": qs.exclude(status__in=[QuickCommerceOrder.Status.DELIVERED, QuickCommerceOrder.Status.CANCELLED]).count(),
                "delivered_orders": qs.filter(status=QuickCommerceOrder.Status.DELIVERED).count(),
                "cancelled_orders": qs.filter(status=QuickCommerceOrder.Status.CANCELLED).count(),
                "avg_eta": qs.aggregate(avg=Avg("promised_eta_minutes"))["avg"] or 0,
                "packing_queue": PackingTask.objects.exclude(status=PackingTask.Status.PACKED).count(),
                "riders_available": RiderProfile.objects.filter(is_available=True).count(),
                "branch_load": list(qs.values("branch__name").annotate(orders=Count("id")).order_by("-orders")[:10]),
            }
        )


class PackingTaskViewSet(RetailModelViewSet):
    queryset = PackingTask.objects.select_related("quick_order", "product", "assigned_to").all()
    serializer_class = PackingTaskSerializer


class RiderProfileViewSet(RetailModelViewSet):
    queryset = RiderProfile.objects.select_related("user", "branch").all()
    serializer_class = RiderProfileSerializer


class DeliveryAllocationViewSet(RetailModelViewSet):
    queryset = DeliveryAllocation.objects.select_related("quick_order", "rider").all()
    serializer_class = DeliveryAllocationSerializer


class RetailAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RetailAuditLog.objects.select_related("actor", "branch").all()
    serializer_class = RetailAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

