from django.contrib import admin

from ai_ocr.models import OCRInvoiceLog


@admin.register(OCRInvoiceLog)
class OCRInvoiceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "status", "reference_type", "reference_id", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("extracted_text", "error", "reference_type")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")

