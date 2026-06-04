from rest_framework import serializers

from performance.models import LeaderboardEntry, Reward, Target


class TargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Target
        fields = [
            "id",
            "user",
            "period",
            "target_value",
            "achieved_value",
            "start_date",
            "end_date",
            "reward",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardEntry
        fields = ["id", "period", "user", "score", "rank", "computed_at"]


class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = ["id", "user", "title", "description", "points", "awarded_at"]

