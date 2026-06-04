from __future__ import annotations

import csv

from django.apps import apps
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import decorators, filters, permissions, response, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication

from . import models
from .permissions import HasDynamicPermission
from .serializers import (
    BusinessSerializer,
    CustomerSerializer,
    CustomEntitySerializer,
    CustomRecordSerializer,
    ExpenseSerializer,
    InvoiceSerializer,
    LedgerAccountSerializer,
    LedgerEntrySerializer,
    MembershipSerializer,
    ModuleSerializer,
    PermissionSerializer,
    ProductSerializer,
    RoleSerializer,
    StoreSerializer,
    SyncQueueSerializer,
    serializer_for_model,
)


def _is_platform_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def _active_memberships(user):
    if not user or not user.is_authenticated:
        return models.UserBusinessMembership.objects.none()
    return (
        models.UserBusinessMembership.objects.filter(user=user, is_active=True)
        .select_related("business", "role")
        .prefetch_related("stores", "role__permissions", "role__permissions__module")
    )


def _legacy_allows_module(user, module):
    checker = getattr(user, "has_permission", None)
    if not callable(checker):
        return False
    for action, _label in models.Permission.ACTIONS:
        if checker(f"{module.key}.{action}") or checker(f"{module.key}_{action}"):
            return True
    return False


def _allowed_modules_and_permissions(user):
    modules = models.Module.objects.filter(is_enabled=True).order_by("order", "name")
    permissions = models.Permission.objects.select_related("module").filter(module__is_enabled=True)

    if _is_platform_admin(user):
        return modules, permissions

    memberships = _active_memberships(user)
    if memberships.filter(role__is_admin=True).exists():
        return modules, permissions

    role_permission_ids = set(
        memberships.filter(role__isnull=False).values_list("role__permissions__id", flat=True)
    )
    role_permission_ids.discard(None)

    module_ids = set(
        permissions.filter(id__in=role_permission_ids).values_list("module_id", flat=True)
    )

    for module in modules:
        if _legacy_allows_module(user, module):
            module_ids.add(module.id)
            role_permission_ids.update(
                permissions.filter(module=module).values_list("id", flat=True)
            )

    return modules.filter(id__in=module_ids), permissions.filter(id__in=role_permission_ids)


def _membership_payload(user):
    payload = []
    for membership in _active_memberships(user):
        payload.append(
            {
                "business": {
                    "id": membership.business_id,
                    "name": membership.business.name,
                    "settings": membership.business.settings,
                },
                "role": None
                if not membership.role
                else {
                    "id": membership.role_id,
                    "key": membership.role.key,
                    "name": membership.role.name,
                    "is_admin": membership.role.is_admin,
                },
                "stores": [
                    {
                        "id": store.id,
                        "name": store.name,
                        "code": store.code,
                        "is_default": store.is_default,
                    }
                    for store in membership.stores.all()
                ],
            }
        )
    return payload


def _permission_payload(permissions):
    rows = []
    for perm in permissions.order_by("module__order", "module__name", "action"):
        rows.append(
            {
                "key": perm.key,
                "label": perm.label,
                "module": perm.module.key,
                "action": perm.action,
            }
        )
    return rows


def _action_map(permissions):
    actions = {}
    for perm in permissions:
        actions.setdefault(perm.module.key, {})[perm.action] = True
    return actions


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


class BaseERPViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasDynamicPermission]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = "__all__"

    @decorators.action(detail=False, methods=["get"])
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        model = queryset.model
        fields = [f.name for f in model._meta.fields]
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{model._meta.model_name}.csv"'
        writer = csv.writer(resp)
        writer.writerow(fields)
        for obj in queryset[:5000]:
            writer.writerow([getattr(obj, field) for field in fields])
        return resp


class BusinessViewSet(BaseERPViewSet):
    queryset = models.Business.objects.all()
    serializer_class = BusinessSerializer
    search_fields = ["name", "mobile", "email", "gst_number"]
    module_key = "businesses"


class StoreViewSet(BaseERPViewSet):
    queryset = models.Store.objects.select_related("business").all()
    serializer_class = StoreSerializer
    search_fields = ["name", "code", "address"]
    module_key = "stores"


class ModuleViewSet(BaseERPViewSet):
    queryset = models.Module.objects.all()
    serializer_class = ModuleSerializer
    search_fields = ["key", "name", "description"]
    module_key = "modules"

    def perform_create(self, serializer):
        module = serializer.save()
        ensure_permissions(module)


class PermissionViewSet(BaseERPViewSet):
    queryset = models.Permission.objects.select_related("module").all()
    serializer_class = PermissionSerializer
    search_fields = ["key", "label", "module__key"]
    module_key = "permissions"


class RoleViewSet(BaseERPViewSet):
    queryset = models.Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    search_fields = ["key", "name"]
    module_key = "roles"


class MembershipViewSet(BaseERPViewSet):
    queryset = models.UserBusinessMembership.objects.select_related("user", "business", "role").prefetch_related("stores").all()
    serializer_class = MembershipSerializer
    search_fields = ["user__email", "user__mobile", "business__name", "role__key"]
    module_key = "users"


class ProductViewSet(BaseERPViewSet):
    queryset = models.Product.objects.select_related("business").all()
    serializer_class = ProductSerializer
    search_fields = ["sku", "barcode", "name", "category"]
    module_key = "products"


class CustomerViewSet(BaseERPViewSet):
    queryset = models.Customer.objects.select_related("business").all()
    serializer_class = CustomerSerializer
    search_fields = ["name", "mobile", "email", "gst_number"]
    module_key = "customers"


class InvoiceViewSet(BaseERPViewSet):
    queryset = models.Invoice.objects.select_related("business", "store", "customer").prefetch_related("lines").all()
    serializer_class = InvoiceSerializer
    search_fields = ["invoice_number", "customer__name", "payment_method", "channel"]
    module_key = "invoices"


class ExpenseViewSet(BaseERPViewSet):
    queryset = models.Expense.objects.select_related("business", "store").all()
    serializer_class = ExpenseSerializer
    search_fields = ["expense_number", "category", "vendor_name", "payment_method"]
    module_key = "expenses"


class LedgerAccountViewSet(BaseERPViewSet):
    queryset = models.LedgerAccount.objects.select_related("business").all()
    serializer_class = LedgerAccountSerializer
    search_fields = ["code", "name", "account_type"]
    module_key = "accounting"


class LedgerEntryViewSet(BaseERPViewSet):
    queryset = models.LedgerEntry.objects.select_related("business", "account").all()
    serializer_class = LedgerEntrySerializer
    search_fields = ["reference", "memo", "account__name"]
    module_key = "accounting"


class CustomEntityViewSet(BaseERPViewSet):
    queryset = models.CustomEntity.objects.select_related("module").all()
    serializer_class = CustomEntitySerializer
    search_fields = ["model_key", "display_name"]
    module_key = "custom_entities"

    def perform_create(self, serializer):
        entity = serializer.save()
        ensure_permissions(entity.module)


class CustomRecordViewSet(BaseERPViewSet):
    queryset = models.CustomRecord.objects.select_related("entity", "business").all()
    serializer_class = CustomRecordSerializer
    search_fields = ["search_text"]
    module_key = "custom_records"

    def get_queryset(self):
        qs = super().get_queryset()
        entity = self.request.query_params.get("entity")
        if entity:
            qs = qs.filter(entity__model_key=entity)
        return qs


class SyncQueueViewSet(BaseERPViewSet):
    queryset = models.SyncQueue.objects.select_related("business").all()
    serializer_class = SyncQueueSerializer
    search_fields = ["device_id", "entity", "operation", "status"]
    module_key = "sync"

    @decorators.action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def push(self, request):
        items = request.data.get("items", [])
        saved = []
        for item in items:
            serializer = self.get_serializer(data=item)
            serializer.is_valid(raise_exception=True)
            saved.append(serializer.save())
        return response.Response({"accepted": len(saved), "status": "queued"})

    @decorators.action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def mark_synced(self, request):
        ids = request.data.get("ids", [])
        updated = models.SyncQueue.objects.filter(id__in=ids).update(status="synced", synced_at=timezone.now())
        return response.Response({"updated": updated})


class DynamicModelViewSet(BaseERPViewSet):
    permission_classes = [HasDynamicPermission]
    module_key = "dynamic_api"

    def _model(self):
        app_label = self.kwargs["app_label"]
        model_name = self.kwargs["model_name"]
        return apps.get_model(app_label, model_name)

    def get_queryset(self):
        return self._model().objects.all()

    def get_serializer_class(self):
        return serializer_for_model(self._model())


@decorators.api_view(["GET"])
@decorators.authentication_classes([JWTAuthentication])
@decorators.permission_classes([permissions.IsAuthenticated])
def dashboard(request):
    sales = models.Invoice.objects.aggregate(total=Sum("grand_total"), count=Count("id"))
    expenses = models.Expense.objects.aggregate(total=Sum("amount"), count=Count("id"))
    low_stock = models.Product.objects.filter(stock_qty__lte=F("low_stock_qty")).count()
    stores = list(models.Store.objects.values("name").annotate(sales=Sum("invoices__grand_total")).order_by("name"))
    recent = list(models.Invoice.objects.select_related("customer").values("invoice_number", "grand_total", "status", "invoice_date", "customer__name")[:8])
    revenue = list(
        models.Invoice.objects.values("invoice_date").annotate(total=Sum("grand_total")).order_by("invoice_date")[:30]
    )
    total_sales = sales["total"] or 0
    total_expenses = expenses["total"] or 0
    return response.Response(
        {
            "brand": "JaisTech ERP",
            "metrics": {
                "sales": total_sales,
                "expenses": total_expenses,
                "profit_loss": total_sales - total_expenses,
                "invoice_count": sales["count"] or 0,
                "customer_count": models.Customer.objects.count(),
                "product_count": models.Product.objects.count(),
                "low_stock_count": low_stock,
            },
            "charts": {
                "revenue_trends": revenue,
                "store_analytics": stores,
                "payment_analytics": list(models.Invoice.objects.values("payment_method").annotate(total=Sum("grand_total"))),
            },
            "recent_invoices": recent,
            "inventory_alerts": list(models.Product.objects.filter(stock_qty__lte=F("low_stock_qty")).values("sku", "name", "stock_qty", "low_stock_qty")[:12]),
        }
    )


@decorators.api_view(["GET"])
@decorators.authentication_classes([JWTAuthentication])
@decorators.permission_classes([permissions.IsAuthenticated])
def reports(request):
    sales = models.Invoice.objects.values("invoice_date").annotate(total=Sum("grand_total"), count=Count("id")).order_by("-invoice_date")[:90]
    expenses = models.Expense.objects.values("expense_date").annotate(total=Sum("amount"), count=Count("id")).order_by("-expense_date")[:90]
    stock = models.Product.objects.values("sku", "name", "stock_qty", "low_stock_qty").order_by("stock_qty")[:100]
    return response.Response(
        {
            "reports": [
                {"key": "sales_report", "title": "Sales Report", "endpoint": "/api/invoices/export/"},
                {"key": "purchase_report", "title": "Purchase Report", "endpoint": "/api/expenses/export/"},
                {"key": "stock_summary", "title": "Stock Summary", "endpoint": "/api/products/export/"},
                {"key": "profit_loss", "title": "Profit & Loss", "endpoint": "/api/dashboard/"},
                {"key": "gst_report", "title": "GST Report", "endpoint": "/api/reports/"},
            ],
            "sales": list(sales),
            "expenses": list(expenses),
            "stock": list(stock),
        }
    )


@decorators.api_view(["GET"])
@decorators.authentication_classes([JWTAuthentication])
@decorators.permission_classes([permissions.IsAuthenticated])
def app_bootstrap(request):
    enabled_modules, permissions_qs = _allowed_modules_and_permissions(request.user)
    permission_rows = list(permissions_qs)
    action_map = _action_map(permission_rows)
    menus = [
        {"key": m.key, "title": m.name, "icon": m.icon, "route": m.app_route, "api": m.api_base, "color": m.color}
        for m in enabled_modules
    ]
    module_flags = {m.key: True for m in enabled_modules}
    return response.Response(
        {
            "app": {
                "name": "JAISTECH",
                "display_name": "JaisTech ERP",
                "api_base_url": "http://127.0.0.1:8080",
                "fastapi_url": "http://127.0.0.1:8000",
            },
            "user": {
                "id": request.user.id,
                "email": getattr(request.user, "email", ""),
                "is_admin": _is_platform_admin(request.user),
                "memberships": _membership_payload(request.user),
            },
            "theme": {
                "primary": "#5B21B6",
                "secondary": "#7C3AED",
                "accent": "#00A884",
                "surface": "#F6F8FB",
                "dark_surface": "#111827",
                "radius": 8,
            },
            "modules": ModuleSerializer(enabled_modules, many=True).data,
            "menus": menus,
            "ui": {
                "modules": module_flags,
                "dashboard": bool(module_flags.get("dashboard") or menus),
                "actions": action_map,
                "bottom_navigation": menus[:5],
            },
            "permissions": _permission_payload(permissions_qs),
            "offline": {"enabled": True, "queue_endpoint": "/api/sync/push/", "pull_endpoint": "/api/dashboard/"},
        }
    )


@decorators.api_view(["GET"])
@decorators.authentication_classes([JWTAuthentication])
@decorators.permission_classes([permissions.IsAuthenticated])
def menu(request):
    modules, _permissions_qs = _allowed_modules_and_permissions(request.user)
    return response.Response(
        [
            {"key": m.key, "title": m.name, "icon": m.icon, "route": m.app_route, "api": m.api_base, "color": m.color}
            for m in modules
        ]
    )


@decorators.api_view(["POST"])
@decorators.authentication_classes([JWTAuthentication])
@decorators.permission_classes([permissions.IsAuthenticated])
def pos_checkout(request):
    serializer = InvoiceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    invoice = serializer.save(channel=request.data.get("channel", "pos"), status="paid")
    return response.Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


def ensure_permissions(module):
    for action, _label in models.Permission.ACTIONS:
        models.Permission.objects.get_or_create(
            module=module,
            action=action,
            defaults={"key": f"{module.key}_{action}", "label": f"{module.name} {_label}"},
        )
