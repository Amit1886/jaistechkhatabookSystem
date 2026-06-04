from __future__ import annotations

from django.core.exceptions import PermissionDenied

from vendors.models import VendorMembership


def can_manage_vendor(*, user, vendor) -> bool:
    u = user
    if not u or not getattr(u, "is_authenticated", False):
        return False
    try:
        if u.groups.filter(name="Super Admin").exists():
            return True
    except Exception:
        pass
    if getattr(vendor, "owner_id", None) == getattr(u, "id", None):
        return True
    try:
        return VendorMembership.objects.filter(vendor=vendor, user=u, is_active=True).exists()
    except Exception:
        return False


def ensure_vendor_access(*, request, vendor) -> None:
    """
    Ensures the authenticated user can manage the given vendor.
    - Vendor owner always allowed.
    - VendorMembership (active) allowed.
    - Super Admin group allowed.
    """
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if can_manage_vendor(user=u, vendor=vendor):
        return
    raise PermissionDenied("You do not have access to this vendor.")
