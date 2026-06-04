from rest_framework import serializers

from api_integrations.models import IntegrationConnection


class IntegrationConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationConnection
        fields = [
            "id",
            "company",
            "provider",
            "name",
            "is_active",
            "credentials",
            "settings",
            "created_by",
            "updated_at",
            "created_at",
        ]
        read_only_fields = ["company", "created_by", "updated_at", "created_at"]

