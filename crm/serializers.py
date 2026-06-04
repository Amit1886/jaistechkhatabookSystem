from rest_framework import serializers

from crm.models import CallLog, CustomerNote, CustomerProfile, FollowUp


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ["id", "user", "company", "last_contacted_at", "lifecycle_stage", "metadata"]


class CustomerNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerNote
        fields = ["id", "customer", "author", "note", "created_at"]
        read_only_fields = ["created_at"]


class CallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = ["id", "customer", "agent", "direction", "duration_seconds", "outcome", "note", "created_at"]
        read_only_fields = ["created_at"]


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = ["id", "customer", "owner", "title", "due_at", "completed_at", "created_at"]
        read_only_fields = ["completed_at", "created_at"]

