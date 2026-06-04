from rest_framework import serializers

from .models import Lead, LeadActivity


class LeadActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadActivity
        fields = ["id", "lead", "actor", "activity_type", "note", "payload", "created_at"]
        read_only_fields = ["created_at"]


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "company",
            "created_by",
            "assigned_to",
            "name",
            "mobile",
            "email",
            "source",
            "status",
            "score",
            "pincode_text",
            "pincode",
            "metadata",
            "next_followup_at",
            "last_contacted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "last_contacted_at"]

