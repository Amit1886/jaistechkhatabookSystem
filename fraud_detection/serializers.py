from rest_framework import serializers

from fraud_detection.models import FraudSignal


class FraudSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudSignal
        fields = [
            "id",
            "company",
            "signal_type",
            "severity",
            "status",
            "user",
            "related_user",
            "description",
            "payload",
            "detected_at",
            "resolved_by",
            "resolved_at",
        ]
        read_only_fields = ["company", "detected_at", "resolved_by", "resolved_at"]

