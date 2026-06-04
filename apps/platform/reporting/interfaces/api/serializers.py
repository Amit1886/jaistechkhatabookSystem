from rest_framework import serializers

from apps.platform.reporting.models import (
    AnalyticsMetric,
    RealtimeDashboardCounter,
    ReportCategory,
    ReportExport,
    ReportRun,
    ReportTemplate,
    SavedReportFilter,
)


class ReportCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportCategory
        fields = "__all__"


class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = "__all__"


class SavedReportFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedReportFilter
        fields = "__all__"


class ReportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRun
        fields = "__all__"
        read_only_fields = fields


class ReportExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportExport
        fields = "__all__"


class AnalyticsMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsMetric
        fields = "__all__"


class RealtimeDashboardCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealtimeDashboardCounter
        fields = "__all__"

