from django.contrib import admin

from ai_insights.models import AIInsight


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "key", "computed_at")
    list_filter = ("key", "computed_at")
    search_fields = ("key",)
    readonly_fields = ("computed_at",)
    ordering = ("-computed_at", "-id")

