from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

from billing.services import get_effective_plan, user_has_feature


class FeatureGateMiddleware(MiddlewareMixin):
    FEATURE_MAP = [
        ("/app/party/", "commerce.suppliers"),
        ("/app/transactions/", "billing.invoices"),
        ("/commerce/product", "commerce.inventory"),
        ("/commerce/orders", "commerce.orders"),
        ("/commerce/sales", "commerce.orders"),
        ("/commerce/purchase", "commerce.orders"),
        ("/procurement/", "procurement.supplier_compare"),
        ("/reports/", "reports.advanced"),
        ("/settings/", "settings.advanced"),
        ("/chatbot/flows/", "chatbot.flows"),
        ("/api/suppliers/", "procurement.supplier_compare"),
        ("/api/supplier-products/", "procurement.supplier_compare"),
        ("/api/best-supplier/", "procurement.supplier_compare"),
        ("/api/supplier-price-history/", "procurement.supplier_compare"),
        ("/api/supplier-ratings/", "procurement.supplier_compare"),
    ]

    # Enforce PlanPermissions on API endpoints (server-side; returns 403 JSON).
    API_PERMISSION_MAP = [
        ("/api/v1/warehouses/", "allow_warehouse"),
        ("/api/v1/products/", "allow_inventory"),
        ("/api/v1/orders/", "allow_orders"),
        ("/api/v1/pos/", "allow_orders"),
        ("/api/v1/printers/", "allow_commerce"),
        ("/api/v1/scanners/", "allow_inventory"),
        ("/api/v1/commission/", "allow_analytics"),
        ("/api/v1/delivery/", "allow_orders"),
        ("/api/v1/payments/", "allow_commerce"),
        ("/api/v1/analytics/", "allow_analytics"),
        ("/api/v1/ai/", "allow_analytics"),
        ("/api/v1/realtime/", "allow_api_access"),
        ("/api/v1/users/", "allow_users"),
    ]

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        path = request.path
        upgrade_url = reverse("billing:upgrade_plan")

        # Admin/staff should never be blocked by plan feature gates.
        if request.user.is_superuser or request.user.is_staff:
            return None

        if path.startswith("/api/"):
            # API: enforce permission flags via effective plan, then fall back to feature registry if needed.
            plan = get_effective_plan(request.user)
            perms = plan.get_permissions() if plan else None

            for prefix, perm_field in self.API_PERMISSION_MAP:
                if path.startswith(prefix):
                    allowed = bool(perms and getattr(perms, perm_field, False))
                    if not allowed:
                        return JsonResponse(
                            {
                                "detail": "Your current plan does not allow this API.",
                                "required_permission": perm_field,
                                "upgrade_url": upgrade_url,
                            },
                            status=403,
                        )
                    break

        for prefix, feature_key in self.FEATURE_MAP:
            if path.startswith(prefix):
                if not user_has_feature(request.user, feature_key):
                    return redirect(upgrade_url)
                break
        return None
