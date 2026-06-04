from django.contrib import admin

from api_integrations.models import IntegrationConnection


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "name", "is_active", "company", "updated_at")
    list_filter = ("provider", "is_active", "company")
    search_fields = ("name",)

