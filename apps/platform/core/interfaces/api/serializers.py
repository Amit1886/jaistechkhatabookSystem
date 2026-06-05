from rest_framework import serializers

from apps.platform.core.models import (
    AutomationRule,
    AutomationRun,
    BackgroundJobDefinition,
    BillOfMaterials,
    ChartOfAccount,
    CommandEnvelope,
    DashboardDefinition,
    DashboardWidget,
    EventSubscription,
    FeatureToggle,
    FormDefinition,
    FormFieldDefinition,
    GSTLedgerEntry,
    IntegrationEndpoint,
    IndustryBlueprint,
    JournalEntry,
    JournalLine,
    MenuItem,
    ModuleDefinition,
    ObservabilityEvent,
    PolicyDefinition,
    ProcurementRequest,
    Product,
    ProductAttribute,
    ProductVariant,
    QueryDefinition,
    ReportDefinition,
    RuleDefinition,
    StockLedgerEntry,
    StockTransfer,
    Warehouse,
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)


class IndustryBlueprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndustryBlueprint
        fields = "__all__"


class FeatureToggleSerializer(serializers.ModelSerializer):
    enabled_now = serializers.SerializerMethodField()

    class Meta:
        model = FeatureToggle
        fields = "__all__"

    def get_enabled_now(self, obj):
        return obj.is_enabled_now()


class ModuleDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleDefinition
        fields = "__all__"


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = "__all__"


class FormFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormFieldDefinition
        fields = "__all__"


class FormDefinitionSerializer(serializers.ModelSerializer):
    fields_detail = FormFieldDefinitionSerializer(source="fields", many=True, read_only=True)

    class Meta:
        model = FormDefinition
        fields = "__all__"


class WorkflowStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowState
        fields = "__all__"


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTransition
        fields = "__all__"


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    states_detail = WorkflowStateSerializer(source="states", many=True, read_only=True)
    transitions_detail = WorkflowTransitionSerializer(source="transitions", many=True, read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = "__all__"


class ReportDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportDefinition
        fields = "__all__"


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = "__all__"


class DashboardDefinitionSerializer(serializers.ModelSerializer):
    widgets_detail = DashboardWidgetSerializer(source="widgets", many=True, read_only=True)

    class Meta:
        model = DashboardDefinition
        fields = "__all__"


class EventSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSubscription
        fields = "__all__"


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = "__all__"


class AutomationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRun
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)


class CommandEnvelopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandEnvelope
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)


class BackgroundJobDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackgroundJobDefinition
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = "__all__"


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = "__all__"


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = "__all__"


class StockLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = StockLedgerEntry
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class StockTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTransfer
        fields = "__all__"


class ProcurementRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementRequest
        fields = "__all__"


class BillOfMaterialsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillOfMaterials
        fields = "__all__"


class ChartOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccount
        fields = "__all__"


class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = "__all__"


class JournalEntrySerializer(serializers.ModelSerializer):
    lines_detail = JournalLineSerializer(source="lines", many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = "__all__"


class GSTLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTLedgerEntry
        fields = "__all__"


class PolicyDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDefinition
        fields = "__all__"


class RuleDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleDefinition
        fields = "__all__"


class QueryDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryDefinition
        fields = "__all__"


class IntegrationEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationEndpoint
        fields = "__all__"


class ObservabilityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObservabilityEvent
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)
    CommandEnvelope,
