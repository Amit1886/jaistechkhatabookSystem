from apps.platform.saas_ecosystem.models import TenantDomain, WhiteLabelProfile


class WhiteLabelService:
    def profile_for_tenant(self, tenant):
        return WhiteLabelProfile.objects.filter(tenant=tenant, is_active=True).first()

    def resolve_domain(self, host):
        return TenantDomain.objects.select_related("tenant").filter(domain=host, is_active=True).first()

    def update_branding(self, tenant, **data):
        profile = self.profile_for_tenant(tenant)
        if not profile:
            profile = WhiteLabelProfile.objects.create(tenant=tenant, brand_name=data.get("brand_name") or tenant.name)
        for field in ("brand_name", "primary_color", "secondary_color", "accent_color", "sidebar_config", "module_config", "invoice_template", "permission_template"):
            if field in data:
                setattr(profile, field, data[field])
        profile.save()
        return profile

