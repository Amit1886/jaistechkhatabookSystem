from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from fastapi import APIRouter, Depends

from enterprise_control.models import APIRegistry
from enterprise_control.services import central_app_config
from fastapi_app.dependencies.auth import current_access_user
from fastapi_app.routers.mobile import current_user_profile


router = APIRouter(prefix="/api/system", tags=["system-app"])


@router.get("/app-config/")
def app_config(platform: str = "app", user=Depends(current_access_user)):
    payload = central_app_config(user=user, platform=platform)
    payload.update(
        {
            "user_context": current_user_profile(platform=platform, user=user),
            "dashboard_config": _dashboard_config(user),
            "reports": _report_payload(user),
            "api_status": _api_status_payload(),
            "live_data": _live_data(user),
        }
    )
    return payload


@router.get("/live-data/")
def live_data(user=Depends(current_access_user)):
    return _live_data(user)


@router.get("/api-status/")
def api_status(user=Depends(current_access_user)):
    return _api_status_payload()


def _dashboard_config(user) -> dict:
    live = _live_data(user)
    sales = live["sales"]
    return {
        "kpis": [
            {"key": "revenue", "label": "Revenue", "value": sales["revenue"], "prefix": "Rs"},
            {"key": "orders", "label": "Orders", "value": sales["orders"]},
            {"key": "invoices", "label": "Invoices", "value": sales["invoices"]},
            {"key": "stock", "label": "Stock Units", "value": sales["stock_units"]},
        ],
        "quick_actions": [
            {"key": "new_pos", "label": "Open POS", "route": "/pos", "module": "pos"},
            {"key": "new_invoice", "label": "Create Invoice", "route": "/billing", "module": "billing"},
            {"key": "add_customer", "label": "Add Customer", "route": "/crm", "module": "crm"},
            {"key": "stock_report", "label": "Stock Report", "route": "/reports", "module": "reports"},
        ],
        "layout": {"columns": 12, "density": "comfortable"},
    }


def _live_data(user) -> dict:
    products = _products(user)
    invoices = _invoices(user)
    customers = _customers(user)
    orders = _orders(user)
    notifications = _notifications(user)
    revenue = sum(_money(item.get("amount")) for item in invoices)
    return {
        "sales": {
            "revenue": str(revenue),
            "orders": len(orders),
            "invoices": len(invoices),
            "customers": len(customers),
            "products": len(products),
            "stock_units": sum(int(item.get("stock") or 0) for item in products),
            "live_users": _active_user_count(),
            "active_devices": _active_device_count(user),
        },
        "products": products,
        "top_products": sorted(products, key=lambda item: item.get("stock") or 0, reverse=True)[:6],
        "invoices": invoices,
        "recent_invoices": invoices[:8],
        "customers": customers,
        "orders": orders,
        "notifications": notifications,
        "reports": _report_payload(user),
        "settings": _settings_payload(user),
    }


def _products(user) -> list[dict]:
    try:
        from commerce.models import Product

        rows = Product.objects.filter(owner=user).select_related("category").order_by("name")[:80]
        if not rows:
            rows = Product.objects.all().select_related("category").order_by("name")[:80]
        return [
            {
                "id": row.id,
                "name": row.name,
                "sku": row.sku,
                "category": getattr(row.category, "name", "") if row.category_id else "",
                "brand": (row.description or "").split("|", 1)[0] if row.description else "",
                "price": str(row.price),
                "stock": row.stock,
                "gst_rate": str(row.gst_rate),
                "unit": row.unit,
            }
            for row in rows
        ]
    except Exception:
        return []


def _customers(user) -> list[dict]:
    try:
        from khataapp.models import Party

        rows = Party.objects.filter(owner=user).order_by("-created_at")[:80]
        if not rows:
            rows = Party.objects.all().order_by("-created_at")[:80]
        return [
            {
                "id": row.id,
                "name": row.name,
                "mobile": row.mobile,
                "email": row.email,
                "type": row.party_type,
                "credit_score": row.credit_score,
                "total_due": str(row.total_due),
                "grade": row.credit_grade,
            }
            for row in rows
        ]
    except Exception:
        return []


def _orders(user) -> list[dict]:
    try:
        from commerce.models import Order

        rows = Order.objects.filter(owner=user).select_related("party").order_by("-created_at")[:80]
        if not rows:
            rows = Order.objects.all().select_related("party").order_by("-created_at")[:80]
        return [
            {
                "id": row.id,
                "customer": getattr(row.party, "name", ""),
                "status": row.status,
                "type": row.order_type,
                "amount": str(row.total_amount()),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    except Exception:
        return []


def _invoices(user) -> list[dict]:
    try:
        from commerce.models import Invoice

        rows = Invoice.objects.filter(order__owner=user).select_related("order", "order__party").order_by("-created_at")[:80]
        if not rows:
            rows = Invoice.objects.all().select_related("order", "order__party").order_by("-created_at")[:80]
        return [
            {
                "id": row.id,
                "number": row.number,
                "customer": getattr(getattr(row.order, "party", None), "name", ""),
                "amount": str(row.amount),
                "status": row.status,
                "gst_type": row.gst_type,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    except Exception:
        return []


def _notifications(user) -> list[dict]:
    try:
        from notifications.models import Notification

        rows = Notification.objects.filter(user=user).order_by("-created_at")[:30]
        return [
            {
                "id": row.id,
                "title": row.title,
                "body": row.body,
                "message": row.body,
                "level": row.level,
                "read": bool(row.read_at),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    except Exception:
        return []


def _report_payload(user) -> list[dict]:
    try:
        from commerce.models import Invoice, Order, Product
        from khataapp.models import Party

        paid = Invoice.objects.filter(order__owner=user, status="paid").aggregate(total=Sum("amount"))["total"] or Decimal("0")
        unpaid = Invoice.objects.filter(order__owner=user, status="unpaid").aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return [
            {"key": "sales_report", "title": "Sales Report", "metric": str(paid + unpaid), "rows": Order.objects.filter(owner=user).count()},
            {"key": "stock_report", "title": "Stock Report", "metric": Product.objects.filter(owner=user).aggregate(total=Sum("stock"))["total"] or 0, "rows": Product.objects.filter(owner=user).count()},
            {"key": "customer_report", "title": "Customer Report", "metric": Party.objects.filter(owner=user, party_type="customer").count(), "rows": Party.objects.filter(owner=user).count()},
            {"key": "gst_report", "title": "GST Report", "metric": str(paid), "rows": Invoice.objects.filter(order__owner=user, gst_type="GST").count()},
        ]
    except Exception:
        return []


def _api_status_payload() -> dict:
    rows = APIRegistry.objects.filter(is_active=True).order_by("module", "endpoint")[:300]
    counts = APIRegistry.objects.values("status").annotate(total=Count("id"))
    return {
        "summary": {row["status"]: row["total"] for row in counts},
        "results": [
            {
                "name": row.name,
                "endpoint": row.endpoint,
                "method": row.method,
                "module": row.module,
                "status": row.status,
                "apps": row.connected_apps,
                "last_status": row.last_response_status,
                "last_error": row.last_error,
            }
            for row in rows
        ],
    }


def _settings_payload(user) -> dict:
    profile = current_user_profile(platform="app", user=user)
    return {
        "profile": profile.get("user", {}),
        "business": profile.get("business", {}),
        "company": profile.get("company", {}),
        "plan": profile.get("subscription_plan", {}),
        "permissions": profile.get("permissions", []),
        "server_time": timezone.now().isoformat(),
    }


def _active_user_count() -> int:
    try:
        from django.contrib.auth import get_user_model

        return get_user_model().objects.filter(is_active=True).count()
    except Exception:
        return 0


def _active_device_count(user) -> int:
    try:
        from enterprise_control.models import DeviceSession

        return DeviceSession.objects.filter(user=user, is_active=True).count()
    except Exception:
        return 0


def _money(value) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")
