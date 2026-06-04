from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.platform.core.models import FeatureToggle, MenuItem, ModuleDefinition
from apps.platform.saas_ecosystem.infrastructure.repositories.saas_repository import SaaSRepository


class TenantProvisioningService:
    def __init__(self, repository=None):
        self.repository = repository or SaaSRepository()

    @transaction.atomic
    def provision(self, *, name, owner_email="", owner=None, plan=None, branding=None):
        if owner is None and owner_email:
            owner = get_user_model().objects.filter(email=owner_email).first()
        slug = slugify(name)[:170]
        tenant, company, branch = self.repository.create_tenant_bundle(name=name, slug=slug, owner=owner)
        self.repository.setup_default_roles(tenant)
        self.repository.setup_branding(tenant, brand_name=(branding or {}).get("brand_name") or name, **(branding or {}))
        self._setup_default_modules(tenant)
        subscription = self.repository.subscribe(tenant, plan) if plan else None
        return {"tenant": tenant, "company": company, "branch": branch, "subscription": subscription}

    def _setup_default_modules(self, tenant):
        modules = [
            ("dashboard", "Dashboard", "platform"),
            ("inventory", "Inventory", "inventory"),
            ("accounting", "Accounting", "financial"),
            ("commerce", "Commerce", "commerce"),
            ("crm", "CRM", "crm"),
        ]
        for index, (key, name, domain) in enumerate(modules, start=1):
            module, _ = ModuleDefinition.objects.get_or_create(tenant=tenant, key=key, defaults={"name": name, "domain": domain})
            MenuItem.objects.get_or_create(
                tenant=tenant,
                key=key,
                defaults={"label": name, "module": module, "url": f"/app/{key}/", "sort_order": index * 10},
            )
            FeatureToggle.objects.get_or_create(tenant=tenant, key=key, defaults={"name": name, "enabled": True})

