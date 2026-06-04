from django.db import OperationalError, ProgrammingError
from django.db.models import Q, Sum

from apps.platform.core.models import (
    AutomationRun,
    AutomationRule,
    DashboardDefinition,
    EventSubscription,
    FeatureToggle,
    FormDefinition,
    JournalEntry,
    JournalLine,
    MenuItem,
    ModuleDefinition,
    ReportDefinition,
    StockLedgerEntry,
    WorkflowDefinition,
    WorkflowTransition,
)

DB_NOT_READY = (OperationalError, ProgrammingError)


class CoreRepository:
    def visible_menu_items(self, tenant=None):
        qs = MenuItem.objects.select_related("tenant", "module", "parent").filter(is_active=True)
        qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
        return qs.order_by("sort_order", "label")

    def active_modules(self, tenant=None):
        qs = ModuleDefinition.objects.filter(is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("domain", "name")

    def feature_toggle(self, key, tenant=None):
        qs = FeatureToggle.objects.filter(key=key, is_active=True).filter(Q(tenant=tenant) | Q(tenant__isnull=True))
        return qs.order_by("-tenant_id").first()

    def form_by_key(self, key, tenant=None):
        qs = FormDefinition.objects.prefetch_related("fields").filter(key=key, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("-tenant_id").first()

    def workflow_by_key(self, key, tenant=None):
        qs = WorkflowDefinition.objects.prefetch_related("states", "transitions").filter(key=key, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("-tenant_id").first()

    def transition_by_key(self, workflow, key):
        return WorkflowTransition.objects.filter(workflow=workflow, key=key, is_active=True).first()

    def report_by_key(self, key, tenant=None):
        qs = ReportDefinition.objects.filter(key=key, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("-tenant_id").first()

    def dashboard_by_key(self, key, tenant=None):
        qs = DashboardDefinition.objects.prefetch_related("widgets").filter(key=key, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("-tenant_id").first()

    def event_subscriptions(self, event_type, tenant=None):
        qs = EventSubscription.objects.filter(event_type=event_type, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("priority", "name")

    def automation_rules(self, event_type, tenant=None):
        qs = AutomationRule.objects.filter(trigger_event=event_type, status=AutomationRule.Status.ACTIVE, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("name")

    def create_automation_run(self, **kwargs):
        return AutomationRun.objects.create(**kwargs)

    def stock_balance(self, tenant, product=None, warehouse=None):
        qs = StockLedgerEntry.objects.filter(tenant=tenant)
        if product is not None:
            qs = qs.filter(product=product)
        if warehouse is not None:
            qs = qs.filter(warehouse=warehouse)
        return qs.values("product_id", "warehouse_id").annotate(quantity=Sum("quantity")).order_by("product_id", "warehouse_id")

    def journal_totals(self, tenant, start_date=None, end_date=None):
        qs = JournalLine.objects.filter(journal__tenant=tenant, journal__status="posted")
        if start_date:
            qs = qs.filter(journal__entry_date__gte=start_date)
        if end_date:
            qs = qs.filter(journal__entry_date__lte=end_date)
        return qs.values("account__account_type", "account__code", "account__name").annotate(
            debit=Sum("debit"),
            credit=Sum("credit"),
        )

    def posted_journal(self, tenant, reference_no):
        return JournalEntry.objects.filter(tenant=tenant, reference_no=reference_no, status="posted").first()

