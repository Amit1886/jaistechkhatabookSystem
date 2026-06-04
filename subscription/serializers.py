from rest_framework import serializers

from billing.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "price", "price_monthly", "price_yearly", "trial_days", "description", "slug", "active"]


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "user", "plan", "status", "start_date", "trial_end", "created_at"]
        read_only_fields = ["status", "start_date", "trial_end", "created_at"]

