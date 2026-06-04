from rest_framework.permissions import BasePermission


class IsVendorUser(BasePermission):
    def has_permission(self, request, view):
        u = getattr(request, "user", None)
        if not u or not u.is_authenticated:
            return False
        return u.groups.filter(name__in=["Vendor", "Vendor Staff", "Super Admin"]).exists()


class IsCustomerUser(BasePermission):
    def has_permission(self, request, view):
        u = getattr(request, "user", None)
        if not u or not u.is_authenticated:
            return False
        return u.groups.filter(name__in=["Customer"]).exists() or getattr(u, "role", "") == "customer"

