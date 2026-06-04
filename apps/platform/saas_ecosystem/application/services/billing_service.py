from decimal import Decimal

from apps.platform.saas_ecosystem.infrastructure.repositories.saas_repository import SaaSRepository
from apps.platform.saas_ecosystem.models import PaymentRetry, SaaSPlan


class SaaSBillingService:
    def __init__(self, repository=None):
        self.repository = repository or SaaSRepository()

    def change_plan(self, tenant, plan_key):
        plan = SaaSPlan.objects.get(key=plan_key, is_active=True)
        current = self.repository.active_subscription(tenant)
        if current:
            current.status = "cancelled"
            current.save(update_fields=["status", "updated_at"])
        return self.repository.subscribe(tenant, plan)

    def meter(self, tenant, metric_key, quantity=1, source_type="", source_id=""):
        return self.repository.record_usage(tenant, metric_key, Decimal(str(quantity)), source_type, source_id)

    def generate_invoice(self, tenant):
        subscription = self.repository.active_subscription(tenant)
        if not subscription:
            return None
        plan = subscription.plan
        line_items = [{"type": "subscription", "description": plan.name, "amount": plan.base_price}]
        for usage in tenant.usagerecord_records.filter(period__isnull=False, metric__billable=True).select_related("metric"):
            line_items.append(
                {
                    "type": "usage",
                    "description": usage.metric.name,
                    "quantity": str(usage.quantity),
                    "amount": usage.quantity * usage.metric.unit_price,
                }
            )
        return self.repository.create_invoice(tenant, subscription, line_items)

    def schedule_retry(self, invoice, attempt_no=1):
        return PaymentRetry.objects.create(invoice=invoice, tenant=invoice.tenant, attempt_no=attempt_no)

