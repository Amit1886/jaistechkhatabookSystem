import uuid

from django.conf import settings
from django.db import models

from apps.platform.identity.models import Tenant


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_records")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class ReportCategory(TimestampedModel):
    key = models.SlugField(max_length=120, unique=True, db_index=True)
    name = models.CharField(max_length=160)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "reporting_categories"
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class ReportTemplate(TenantScopedModel):
    class ReportType(models.TextChoices):
        TABLE = "table", "Table"
        KPI = "kpi", "KPI"
        CHART = "chart", "Chart"
        PIVOT = "pivot", "Pivot"
        STATEMENT = "statement", "Statement"

    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    category = models.ForeignKey(ReportCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="templates")
    report_type = models.CharField(max_length=30, choices=ReportType.choices, default=ReportType.TABLE, db_index=True)
    domain = models.CharField(max_length=80, db_index=True)
    source_model = models.CharField(max_length=160, blank=True, default="")
    query_spec = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=list, blank=True)
    chart_spec = models.JSONField(default=dict, blank=True)
    permission_key = models.CharField(max_length=180, blank=True, default="")
    cache_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "reporting_templates"
        unique_together = ("tenant", "key")
        ordering = ("domain", "name")

    def __str__(self):
        return self.name


class SavedReportFilter(TenantScopedModel):
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name="saved_filters")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_report_filters")
    name = models.CharField(max_length=160)
    filters = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "reporting_saved_filters"
        unique_together = ("template", "user", "name")


class ReportRun(TenantScopedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="report_runs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True)
    filters = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    result_preview = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "reporting_runs"
        ordering = ("-created_at",)


class ReportExport(TenantScopedModel):
    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        EXCEL = "excel", "Excel"
        CSV = "csv", "CSV"
        PRINT = "print", "Print"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    run = models.ForeignKey(ReportRun, on_delete=models.CASCADE, related_name="exports")
    export_format = models.CharField(max_length=20, choices=Format.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    file = models.FileField(upload_to="report_exports/", null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "reporting_exports"
        ordering = ("-created_at",)


class AnalyticsMetric(TenantScopedModel):
    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    domain = models.CharField(max_length=80, db_index=True)
    value = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    period = models.CharField(max_length=30, blank=True, default="", db_index=True)
    dimension = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "reporting_analytics_metrics"
        unique_together = ("tenant", "key", "period")
        ordering = ("domain", "key")


class RealtimeDashboardCounter(TenantScopedModel):
    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    value = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    channel = models.CharField(max_length=120, default="reports", db_index=True)

    class Meta:
        db_table = "reporting_realtime_counters"
        unique_together = ("tenant", "key")

