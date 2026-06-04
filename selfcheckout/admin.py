from django.contrib import admin

from .models import (
    CheckoutCartItem,
    CheckoutSession,
    CustomerMembership,
    CustomerOTPChallenge,
    KioskDevice,
    KioskEvent,
    KioskInteractionEvent,
    MobileContinueSession,
    PromoMedia,
    QueueTicket,
    RetailBroadcast,
    RetailSyncSnapshot,
    RewardCampaign,
    RewardDrop,
    SupportRequest,
)


class CheckoutCartItemInline(admin.TabularInline):
    model = CheckoutCartItem
    extra = 0


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ("session_key", "owner", "kiosk_id", "customer", "customer_mode", "customer_verified", "status", "applied_coupon", "total", "started_at", "completed_at")
    list_filter = ("status", "kiosk_id", "customer_mode", "customer_verified", "applied_coupon")
    search_fields = ("session_key", "payment_reference", "customer__name", "customer__mobile", "guest_reference")
    inlines = [CheckoutCartItemInline]


@admin.register(KioskDevice)
class KioskDeviceAdmin(admin.ModelAdmin):
    list_display = ("kiosk_id", "name", "zone", "status", "scanner_status", "printer_status", "payment_status", "internet_status", "cpu_usage", "memory_usage", "last_seen_at")
    list_filter = ("status", "zone", "scanner_status", "payment_status")
    search_fields = ("kiosk_id", "name", "zone")


@admin.register(QueueTicket)
class QueueTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_code", "owner", "status", "assigned_kiosk", "estimated_wait_seconds", "created_at", "assigned_at")
    list_filter = ("status", "assigned_kiosk")
    search_fields = ("ticket_code", "owner__username", "owner__email")


@admin.register(KioskEvent)
class KioskEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "severity", "session", "kiosk", "message", "created_at")
    list_filter = ("event_type", "severity", "kiosk")
    search_fields = ("message", "session__session_key", "kiosk__kiosk_id")


@admin.register(CustomerMembership)
class CustomerMembershipAdmin(admin.ModelAdmin):
    list_display = ("member_code", "party", "tier", "wallet_balance", "welcome_coupon", "welcome_awarded", "is_blocked", "last_seen_at")
    list_filter = ("tier", "welcome_awarded", "is_blocked", "consent_face")
    search_fields = ("member_code", "qr_token", "nfc_uid", "party__name", "party__mobile")


@admin.register(CustomerOTPChallenge)
class CustomerOTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("mobile", "purpose", "session", "is_verified", "attempts", "expires_at", "created_at")
    list_filter = ("purpose", "is_verified")
    search_fields = ("mobile", "session__session_key")


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "kiosk", "issue_type", "priority", "status", "customer_name", "opened_at", "assigned_at", "resolved_at")
    list_filter = ("status", "priority", "issue_type", "kiosk")
    search_fields = ("session__session_key", "kiosk__kiosk_id", "customer_name", "notes")
    readonly_fields = ("opened_at",)


@admin.register(KioskInteractionEvent)
class KioskInteractionEventAdmin(admin.ModelAdmin):
    list_display = ("kind", "area", "kiosk_id", "product", "intensity", "duration_ms", "created_at")
    list_filter = ("kind", "area", "kiosk_id")
    search_fields = ("area", "product__name", "session__session_key")
    readonly_fields = ("created_at",)


@admin.register(MobileContinueSession)
class MobileContinueSessionAdmin(admin.ModelAdmin):
    list_display = ("session", "device_label", "is_active", "created_at", "last_seen_at", "expires_at")
    list_filter = ("is_active", "device_label")
    search_fields = ("token", "session__session_key", "session__kiosk_id")


@admin.register(RewardCampaign)
class RewardCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "coupon_code", "cashback_amount", "probability", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "coupon_code", "owner__email")


@admin.register(RewardDrop)
class RewardDropAdmin(admin.ModelAdmin):
    list_display = ("title", "session", "campaign", "reward_type", "coupon_code", "cashback_amount", "created_at")
    list_filter = ("reward_type", "campaign")
    search_fields = ("title", "coupon_code", "session__session_key")


@admin.register(PromoMedia)
class PromoMediaAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "product", "badge", "is_active", "starts_at", "ends_at")
    list_filter = ("is_active", "badge")
    search_fields = ("title", "badge", "product__name", "owner__email")


@admin.register(RetailBroadcast)
class RetailBroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "priority", "voice_enabled", "is_active", "starts_at", "expires_at", "created_at")
    list_filter = ("priority", "voice_enabled", "is_active")
    search_fields = ("title", "message", "owner__email")


@admin.register(RetailSyncSnapshot)
class RetailSyncSnapshotAdmin(admin.ModelAdmin):
    list_display = ("owner", "key", "version", "updated_at")
    list_filter = ("key",)
    search_fields = ("owner__email", "key")
    readonly_fields = ("updated_at",)
