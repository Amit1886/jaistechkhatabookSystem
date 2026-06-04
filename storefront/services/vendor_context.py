from __future__ import annotations

from rest_framework.exceptions import PermissionDenied, ValidationError

from vendors.models import Vendor
from vendors.models import VendorMembership


def get_vendor_from_request(request) -> Vendor:
    vendor = getattr(request, "vendor", None)
    if vendor:
        return vendor

    # Best-effort: infer vendor from authenticated user (owner or single membership).
    u = getattr(request, "user", None)
    if u and getattr(u, "is_authenticated", False):
        owner_vendor = getattr(u, "vendor", None)
        if owner_vendor and getattr(owner_vendor, "is_active", False):
            return owner_vendor
        membership_qs = VendorMembership.objects.filter(user=u, is_active=True, vendor__is_active=True).select_related("vendor")
        if membership_qs.count() == 1:
            return membership_qs.first().vendor

    vendor_id = None
    if hasattr(request, "query_params"):
        vendor_id = request.query_params.get("vendor_id")
    if not vendor_id and hasattr(request, "data"):
        vendor_id = request.data.get("vendor_id")

    if vendor_id:
        v = Vendor.objects.filter(id=vendor_id, is_active=True).first()
        if v:
            # Ensure user has access to the requested vendor.
            if u and getattr(u, "is_authenticated", False):
                if u.groups.filter(name="Super Admin").exists():
                    return v
                if getattr(v, "owner_id", None) == u.id:
                    return v
                if VendorMembership.objects.filter(vendor=v, user=u, is_active=True).exists():
                    return v
                raise PermissionDenied("You do not have access to this vendor.")
            return v
    raise ValidationError({"vendor": "Vendor not resolved. Use vendor subdomain or pass vendor_id."})
