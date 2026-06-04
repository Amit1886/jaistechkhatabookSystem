from django.contrib import admin

from apps.platform.reporting.models import (
    AnalyticsMetric,
    RealtimeDashboardCounter,
    ReportCategory,
    ReportExport,
    ReportRun,
    ReportTemplate,
    SavedReportFilter,
)


@admin.register(ReportCategory)
class ReportCategoryAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "sort_order", "is_active")
    search_fields = ("key", "name")
    list_filter = ("is_active",)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "domain", "report_type", "category", "tenant", "is_active")
    search_fields = ("key", "name", "source_model")
    list_filter = ("domain", "report_type", "category", "tenant", "is_active")


@admin.register(SavedReportFilter)
class SavedReportFilterAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "user", "tenant", "is_default", "is_active")
    search_fields = ("name", "template__key", "user__email")
    list_filter = ("is_default", "tenant", "is_active")


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "template", "user", "tenant", "status", "row_count", "duration_ms")
    search_fields = ("template__key", "user__email", "error")
    list_filter = ("status", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in ReportRun._meta.fields)


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "run", "export_format", "status", "tenant")
    search_fields = ("run__template__key", "error")
    list_filter = ("export_format", "status", "tenant", "created_at")


@admin.register(AnalyticsMetric)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "domain", "value", "period", "tenant", "is_active")
    search_fields = ("key", "name", "period")
    list_filter = ("domain", "tenant", "is_active")


@admin.register(RealtimeDashboardCounter)
class RealtimeDashboardCounterAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "value", "channel", "tenant", "is_active")
    search_fields = ("key", "name")
    list_filter = ("channel", "tenant", "is_active")

