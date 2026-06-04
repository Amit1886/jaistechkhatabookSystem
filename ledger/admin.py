from __future__ import annotations

from django.contrib import admin

from ledger.models import (
    JournalVoucher,
    JournalVoucherLine,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    Receipt,
    ReturnNote,
    ReturnNoteItem,
    StockLedger,
    StockTransfer,
    StockTransferItem,
)


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "owner", "party", "is_system")
    list_filter = ("account_type", "is_system")
    search_fields = ("code", "name", "party__name", "owner__username", "owner__email")
    raw_id_fields = ("owner", "party")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("code",)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj=obj))
        if obj:
            # keep identifiers stable after creation
            ro.extend(["owner", "code", "party"])
        if obj and obj.is_system and "is_system" not in ro:
            ro.append("is_system")
        return ro


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    raw_id_fields = ("account", "party")
    fields = ("line_no", "account", "party", "description", "debit", "credit")
    ordering = ("line_no", "id")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "owner",
        "voucher_type",
        "reference_no",
        "reference_type",
        "reference_id",
        "total_debit",
        "total_credit",
    )
    list_filter = ("voucher_type", "date")
    search_fields = ("reference_no", "reference_type", "narration")
    raw_id_fields = ("owner",)
    date_hierarchy = "date"
    inlines = [LedgerEntryInline]
    ordering = ("-date", "-id")

    def get_readonly_fields(self, request, obj=None):
        # GL transactions are system-generated; keep them read-only in admin.
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "line_no", "account", "party", "debit", "credit")
    list_filter = ("account",)
    search_fields = ("transaction__reference_no", "account__code", "account__name", "description")
    raw_id_fields = ("transaction", "account", "party")
    ordering = ("-id",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("transaction", "account", "party")

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "owner", "kind", "reference_type", "reference_id", "voucher_type", "gst_enabled")
    list_filter = ("kind", "gst_enabled", "created_at")
    search_fields = ("receipt_no", "reference_type", "reference_id", "voucher_type")
    raw_id_fields = ("owner", "gl_transaction")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "owner",
        "product",
        "warehouse",
        "movement",
        "quantity_in",
        "quantity_out",
        "reference_type",
        "reference_id",
    )
    list_filter = ("movement", "date", "warehouse")
    search_fields = ("product__name", "reference_type", "reference_id")
    raw_id_fields = ("owner", "product", "warehouse")
    date_hierarchy = "date"
    ordering = ("-date", "-id")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("owner", "product", "warehouse")

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 0
    raw_id_fields = ("product",)
    fields = ("product", "quantity")


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "owner", "from_warehouse", "to_warehouse", "status")
    list_filter = ("status", "date")
    search_fields = ("id", "notes", "from_warehouse__name", "to_warehouse__name")
    raw_id_fields = ("owner", "from_warehouse", "to_warehouse")
    date_hierarchy = "date"
    inlines = [StockTransferItemInline]
    ordering = ("-date", "-id")


class JournalVoucherLineInline(admin.TabularInline):
    model = JournalVoucherLine
    extra = 0
    raw_id_fields = ("account", "party")
    fields = ("account", "party", "description", "debit", "credit")


@admin.register(JournalVoucher)
class JournalVoucherAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "owner", "status")
    list_filter = ("status", "date")
    search_fields = ("id", "narration")
    raw_id_fields = ("owner",)
    date_hierarchy = "date"
    inlines = [JournalVoucherLineInline]
    ordering = ("-date", "-id")


class ReturnNoteItemInline(admin.TabularInline):
    model = ReturnNoteItem
    extra = 0
    raw_id_fields = ("product",)
    fields = ("product", "quantity", "rate")


@admin.register(ReturnNote)
class ReturnNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "owner", "note_type", "status", "invoice", "total_amount")
    list_filter = ("note_type", "status", "date")
    search_fields = ("id", "narration", "invoice__number")
    raw_id_fields = ("owner", "invoice")
    date_hierarchy = "date"
    inlines = [ReturnNoteItemInline]
    ordering = ("-date", "-id")
