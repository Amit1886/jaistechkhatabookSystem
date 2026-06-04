from django.contrib import admin

from wallet.models import Wallet, WalletTransaction, WithdrawRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "currency", "updated_at")
    search_fields = ("user__email",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "entry_type", "amount", "source", "created_at")
    list_filter = ("entry_type", "source")


@admin.register(WithdrawRequest)
class WithdrawRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "user", "amount", "status", "requested_at", "processed_at")
    list_filter = ("status",)
