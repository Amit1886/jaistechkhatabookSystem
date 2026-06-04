from rest_framework import serializers

from .models import AgentCustomerAssignment


class AgentCustomerAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCustomerAssignment
        fields = [
            "id",
            "company",
            "customer",
            "agent",
            "assigned_by",
            "assigned_at",
            "unassigned_at",
            "reason",
            "metadata",
        ]
        read_only_fields = ["assigned_at", "unassigned_at"]

