from django.contrib import admin

from bank_import.models import BankImportLog


@admin.register(BankImportLog)
class BankImportLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("error",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")

