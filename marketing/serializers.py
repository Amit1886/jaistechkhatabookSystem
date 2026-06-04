from rest_framework import serializers

from marketing.models import Campaign, CampaignMessage


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "company",
            "created_by",
            "channel",
            "status",
            "name",
            "audience",
            "ai_prompt",
            "ad_copy",
            "metadata",
            "scheduled_at",
            "started_at",
            "completed_at",
            "last_error",
            "recipients_total",
            "recipients_sent",
            "recipients_failed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["started_at", "completed_at", "last_error", "recipients_total", "recipients_sent", "recipients_failed", "created_at", "updated_at"]


class CampaignMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignMessage
        fields = ["id", "campaign", "lead", "user", "destination", "payload", "status", "provider_ref", "last_error", "created_at", "sent_at"]
        read_only_fields = ["created_at", "sent_at", "provider_ref", "last_error"]

