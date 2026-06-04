from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


@dataclass(frozen=True)
class VendorResolution:
    subdomain: str = ""


def _host_without_port(host: str) -> str:
    host = (host or "").strip()
    if not host:
        return ""
    return host.split(":", 1)[0].strip().lower()


def _resolve_vendor_subdomain(host: str) -> VendorResolution:
    host = _host_without_port(host)
    if not host:
        return VendorResolution()

    excluded = set(
        (getattr(settings, "VENDOR_SUBDOMAIN_EXCLUDED_HOSTS", None) or ["localhost", "127.0.0.1", "testserver"])
    )
    if host in excluded:
        return VendorResolution()

    base_domain = (getattr(settings, "MARKETPLACE_BASE_DOMAIN", "") or "").strip().lower()

    if host.endswith(".localhost"):
        sub = host[: -len(".localhost")].strip(".")
        return VendorResolution(subdomain=sub)

    if base_domain and host.endswith("." + base_domain):
        sub = host[: -(len(base_domain) + 1)]
        return VendorResolution(subdomain=sub.strip("."))

    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3:
        return VendorResolution(subdomain=parts[0])
    return VendorResolution()


class VendorSubdomainMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.vendor = None
        request.vendor_subdomain = ""
        res = _resolve_vendor_subdomain(request.get_host())
        if not res.subdomain:
            return None

        from .models import Vendor

        vendor = (
            Vendor.objects.select_related("owner", "primary_warehouse")
            .filter(subdomain=res.subdomain, is_active=True)
            .first()
        )
        request.vendor = vendor
        request.vendor_subdomain = res.subdomain
        return None

