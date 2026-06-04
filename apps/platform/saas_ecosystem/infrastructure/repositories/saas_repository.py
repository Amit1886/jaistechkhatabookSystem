from django.db import transaction
from django.utils import timezone

from apps.platform.identity.models import Branch, Company, EnterprisePermission, EnterpriseRole, RolePermission, Tenant, TenantMembership
from apps.platform.saas_ecosystem.models import (
    SaaSInvoice,
    SaaSPlan,
    TenantSubscription,
    UsageMetric,
    UsageRecord,
    WhiteLabelProfile,
)


class SaaSRepository:
    @transaction.atomic
    def create_tenant_bundle(self, *, name, slug, owner=None, company_name="", branch_name="Main"):
        tenant = Tenant.objects.create(name=name, slug=slug, owner=owner)
        company = Company.objects.create(tenant=tenant, name=company_name or name)
        branch = Branch.objects.create(tenant=tenant, company=company, name=branch_name, code="MAIN")
        if owner:
            TenantMembership.objects.create(tenant=tenant, company=company, branch=branch, user=owner, is_owner=True)
        return tenant, company, branch

    def setup_default_roles(self, tenant):
        admin_role, _ = EnterpriseRole.objects.get_or_create(
            tenant=tenant,
            key="tenant-admin",
            defaults={"name": "Tenant Admin", "is_system": True},
        )
        for key, label in (
            ("tenant.manage", "Manage Tenant"),
            ("billing.manage", "Manage Billing"),
            ("modules.manage", "Manage Modules"),
            ("users.manage", "Manage Users"),
        ):
            permission, _ = EnterprisePermission.objects.get_or_create(
                tenant=tenant,
                key=key,
                defaults={"label": label, "scope": "action"},
            )
            RolePermission.objects.get_or_create(role=admin_role, permission=permission, defaults={"allowed": True})
        return admin_role

    def setup_branding(self, tenant, brand_name=None, **kwargs):
        profile, _ = WhiteLabelProfile.objects.get_or_create(
            tenant=tenant,
            brand_name=brand_name or tenant.name,
            defaults=kwargs,
        )
        return profile

    def active_subscription(self, tenant):
        return TenantSubscription.objects.filter(tenant=tenant, status__in=["trial", "active", "past_due"]).select_related("plan").first()

    def subscribe(self, tenant, plan: SaaSPlan):
        now = timezone.now()
        trial_end = now + timezone.timedelta(days=plan.trial_days) if plan.trial_days else None
        period_end = now + (timezone.timedelta(days=365) if plan.interval == "yearly" else timezone.timedelta(days=30))
        return TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.Status.TRIAL if trial_end else TenantSubscription.Status.ACTIVE,
            current_period_start=now,
            current_period_end=period_end,
            trial_end=trial_end,
        )

    def record_usage(self, tenant, metric_key, quantity, source_type="", source_id=""):
        metric, _ = UsageMetric.objects.get_or_create(key=metric_key, defaults={"name": metric_key.replace("-", " ").title()})
        period = timezone.now().strftime("%Y-%m")
        return UsageRecord.objects.create(
            tenant=tenant,
            metric=metric,
            quantity=quantity,
            period=period,
            source_type=source_type,
            source_id=source_id,
        )

    def create_invoice(self, tenant, subscription, line_items):
        subtotal = sum(item.get("amount", 0) for item in line_items)
        tax = subtotal * 0.18
        total = subtotal + tax
        invoice_no = f"SAAS-{timezone.now().strftime('%Y%m%d%H%M%S')}-{str(tenant.id)[:6]}"
        return SaaSInvoice.objects.create(
            tenant=tenant,
            subscription=subscription,
            invoice_number=invoice_no,
            status=SaaSInvoice.Status.ISSUED,
            subtotal=subtotal,
            tax_amount=tax,
            total=total,
            due_at=timezone.now() + timezone.timedelta(days=7),
            line_items=line_items,
        )

