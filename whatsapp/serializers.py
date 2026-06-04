from __future__ import annotations

from rest_framework import serializers

from whatsapp.models import (
    Bot,
    BotFlow,
    BotMessage,
    BotTemplate,
    BroadcastCampaign,
    Customer,
    WhatsAppAccount,
    WhatsAppMessage,
)


def _mask(value: str, keep_last: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return ("*" * (len(value) - keep_last)) + value[-keep_last:]


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    meta_access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meta_app_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    gateway_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    webhook_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    meta_access_token_masked = serializers.SerializerMethodField()
    meta_app_secret_masked = serializers.SerializerMethodField()
    gateway_api_key_masked = serializers.SerializerMethodField()
    webhook_secret_masked = serializers.SerializerMethodField()
    meta_webhook_url = serializers.SerializerMethodField()
    gateway_webhook_url = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppAccount
        fields = [
            "id",
            "label",
            "phone_number",
            "provider",
            "is_active",
            "status",
            "last_seen_at",
            "created_at",
            "updated_at",
            # Quick commerce
            "quick_commerce_enabled",
            "quick_delivery_radius_km",
            "store_latitude",
            "store_longitude",
            "quick_assign_agent",
            # Meta Cloud
            "meta_phone_number_id",
            "meta_waba_id",
            "meta_graph_version",
            "meta_verify_token",
            "meta_access_token",
            "meta_app_secret",
            "meta_access_token_masked",
            "meta_app_secret_masked",
            "meta_webhook_url",
            # Gateway
            "gateway_base_url",
            "gateway_session_id",
            "gateway_api_key",
            "gateway_api_key_masked",
            "webhook_secret",
            "webhook_secret_masked",
            "gateway_webhook_url",
        ]
        read_only_fields = ["status", "last_seen_at", "created_at", "updated_at", "meta_verify_token"]

    def get_meta_access_token_masked(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "meta_access_token", ""))

    def get_meta_app_secret_masked(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "meta_app_secret", ""))

    def get_gateway_api_key_masked(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "gateway_api_key", ""))

    def get_webhook_secret_masked(self, obj: WhatsAppAccount) -> str:
        return _mask(getattr(obj, "webhook_secret", ""))

    def get_meta_webhook_url(self, obj: WhatsAppAccount) -> str:
        request = self.context.get("request")
        if not request:
            return ""
        try:
            from django.urls import reverse

            return request.build_absolute_uri(reverse("whatsapp_meta_webhook", kwargs={"account_id": str(obj.id)}))
        except Exception:
            return ""

    def get_gateway_webhook_url(self, obj: WhatsAppAccount) -> str:
        request = self.context.get("request")
        if not request:
            return ""
        try:
            from django.urls import reverse

            return request.build_absolute_uri(reverse("whatsapp_gateway_inbound_webhook", kwargs={"account_id": str(obj.id)}))
        except Exception:
            return ""

    def create(self, validated_data):
        request = self.context.get("request")
        owner = validated_data.pop("owner", None) or getattr(request, "user", None)
        token = validated_data.pop("meta_access_token", None)
        secret = validated_data.pop("meta_app_secret", None)
        gw_key = validated_data.pop("gateway_api_key", None)
        wh_secret = validated_data.pop("webhook_secret", None)

        acc = WhatsAppAccount.objects.create(owner=owner, **validated_data)
        if token is not None:
            acc.meta_access_token = token
        if secret is not None:
            acc.meta_app_secret = secret
        if gw_key is not None:
            acc.gateway_api_key = gw_key
        if wh_secret is not None:
            acc.webhook_secret = wh_secret
        acc.save()
        return acc

    def update(self, instance: WhatsAppAccount, validated_data):
        token = validated_data.pop("meta_access_token", None)
        secret = validated_data.pop("meta_app_secret", None)
        gw_key = validated_data.pop("gateway_api_key", None)
        wh_secret = validated_data.pop("webhook_secret", None)

        for k, v in validated_data.items():
            setattr(instance, k, v)
        if token is not None:
            instance.meta_access_token = token
        if secret is not None:
            instance.meta_app_secret = secret
        if gw_key is not None:
            instance.gateway_api_key = gw_key
        if wh_secret is not None:
            instance.webhook_secret = wh_secret
        instance.save()
        return instance


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = [
            "id",
            "whatsapp_account",
            "name",
            "kind",
            "is_enabled",
            "auto_reply_enabled",
            "ai_fallback_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class BotMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotMessage
        fields = ["id", "bot", "key", "message_type", "text", "media_url", "filename", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class BotFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotFlow
        fields = [
            "id",
            "bot",
            "name",
            "description",
            "trigger_type",
            "trigger_value",
            "trigger_payload",
            "actions",
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "whatsapp_account",
            "phone_number",
            "display_name",
            "party",
            "tags",
            "last_seen_at",
            "last_location_lat",
            "last_location_lng",
            "last_location_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["last_seen_at", "last_location_lat", "last_location_lng", "last_location_at", "created_at", "updated_at"]


class BroadcastCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = BroadcastCampaign
        fields = [
            "id",
            "whatsapp_account",
            "name",
            "status",
            "target_type",
            "target_payload",
            "message_type",
            "text",
            "media_url",
            "scheduled_at",
            "started_at",
            "finished_at",
            "stats",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["started_at", "finished_at", "stats", "error", "created_at", "updated_at"]


class BotTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotTemplate
        fields = ["id", "owner", "name", "kind", "description", "payload", "is_active", "created_at", "updated_at"]
        read_only_fields = ["owner", "created_at", "updated_at"]


class WhatsAppMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = [
            "id",
            "whatsapp_account",
            "customer",
            "direction",
            "message_type",
            "provider_message_id",
            "from_number",
            "to_number",
            "body",
            "parsed_intent",
            "parsed_payload",
            "reference_type",
            "reference_id",
            "status",
            "error",
            "created_at",
        ]
        read_only_fields = ["created_at"]
