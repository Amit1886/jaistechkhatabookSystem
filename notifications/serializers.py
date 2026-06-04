from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "company", "user", "title", "body", "level", "data", "read_at", "created_at"]
        read_only_fields = ["company", "user", "created_at"]

