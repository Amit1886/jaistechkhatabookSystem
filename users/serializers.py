from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import CommissionLedger, UserProfileExt, WalletLedger


User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "mobile"]


class UserProfileExtSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = UserProfileExt
        fields = "__all__"


class WalletLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletLedger
        fields = "__all__"


class CommissionLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionLedger
        fields = "__all__"


class SubUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "mobile",
            "is_active",
            "store_type",
            "primary_role",
            "permissions_json",
            "parent_id",
            "seller_id",
        ]
        read_only_fields = ["id", "parent_id", "seller_id"]
