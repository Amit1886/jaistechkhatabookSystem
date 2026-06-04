from django.contrib import admin

from whatsapp.models import (
    Bot,
    BotFlow,
    BotMessage,
    BotTemplate,
    BroadcastCampaign,
    Customer,
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppOperator,
    WhatsAppSession,
)


def _mask(value: str, keep_last: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return ("*" * (len(value) - keep_last)) + value[-keep_last:]


@admin.register(WhatsAppAccount)
class WhatsAppAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "label",
        "phone_number",
        "provider",
        "status",
        "is_active",
        "quick_commerce_enabled",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("provider", "status", "is_active", "quick_commerce_enabled", "updated_at")
    search_fields = ("label", "phone_number", "meta_phone_number_id", "meta_waba_id", "gateway_session_id")
    readonly_fields = ("id", "created_at", "updated_at", "last_seen_at")
    ordering = ("-updated_at", "-created_at")

    def masked_meta_access_token(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "meta_access_token", ""))

    def masked_gateway_api_key(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "gateway_api_key", ""))

    def masked_webhook_secret(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "webhook_secret", ""))


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "status", "provider_session_id", "last_qr_at", "last_connected_at", "updated_at")
    list_filter = ("status", "updated_at")
    search_fields = ("provider_session_id", "account__label", "account__phone_number")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-updated_at", "-created_at")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "whatsapp_account", "display_name", "phone_number", "party", "last_seen_at", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("display_name", "phone_number", "party__name", "party__mobile", "party__whatsapp_number")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    ordering = ("-updated_at", "-created_at")


@admin.register(WhatsAppOperator)
class WhatsAppOperatorAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "whatsapp_account", "display_name", "phone_number", "role", "is_active", "updated_at")
    list_filter = ("role", "is_active", "updated_at")
    search_fields = ("display_name", "phone_number", "whatsapp_account__label", "whatsapp_account__phone_number", "owner__email", "owner__mobile")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-updated_at", "-created_at")


class BotFlowInline(admin.TabularInline):
    model = BotFlow
    extra = 0


class BotMessageInline(admin.TabularInline):
    model = BotMessage
    extra = 0


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "whatsapp_account", "name", "kind", "is_enabled", "auto_reply_enabled", "ai_fallback_enabled", "updated_at")
    list_filter = ("kind", "is_enabled", "auto_reply_enabled", "ai_fallback_enabled", "updated_at")
    search_fields = ("name", "whatsapp_account__label", "whatsapp_account__phone_number")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-updated_at", "-created_at")
    inlines = [BotFlowInline, BotMessageInline]


@admin.register(BroadcastCampaign)
class BroadcastCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "whatsapp_account", "name", "status", "target_type", "scheduled_at", "updated_at")
    list_filter = ("status", "target_type", "updated_at")
    search_fields = ("name", "whatsapp_account__label", "whatsapp_account__phone_number")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "finished_at")
    ordering = ("-updated_at", "-created_at")


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "whatsapp_account",
        "direction",
        "message_type",
        "from_number",
        "to_number",
        "parsed_intent",
        "status",
        "created_at",
    )
    list_filter = ("direction", "status", "message_type", "parsed_intent", "created_at")
    search_fields = ("from_number", "to_number", "provider_message_id", "error", "reference_type")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(BotTemplate)
class BotTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "name", "kind", "is_active", "updated_at")
    list_filter = ("kind", "is_active", "updated_at")
    search_fields = ("name", "description", "owner__email", "owner__mobile")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-updated_at", "-created_at")
