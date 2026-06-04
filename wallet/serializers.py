from rest_framework import serializers

from wallet.models import Wallet, WalletTransaction, WithdrawRequest


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["id", "user", "balance", "currency", "updated_at", "created_at"]
        read_only_fields = ["balance", "updated_at", "created_at"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ["id", "wallet", "entry_type", "amount", "source", "reference", "metadata", "created_at"]
        read_only_fields = ["created_at"]


class WithdrawRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawRequest
        fields = [
            "id",
            "wallet",
            "user",
            "amount",
            "status",
            "requested_at",
            "processed_at",
            "processed_by",
            "payout_reference",
            "metadata",
        ]
        read_only_fields = ["status", "requested_at", "processed_at", "processed_by", "payout_reference"]

