from __future__ import annotations

from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone


def _count(model_path: str, **filters) -> int:
    try:
        app_label, model_name = model_path.split(".", 1)
        from django.apps import apps

        model = apps.get_model(app_label, model_name)
        return int(model.objects.filter(**filters).count())
    except Exception:
        return 0


def _sum(model_path: str, field: str, **filters) -> Decimal:
    try:
        app_label, model_name = model_path.split(".", 1)
        from django.apps import apps

        model = apps.get_model(app_label, model_name)
        value = model.objects.filter(**filters).aggregate(total=Sum(field)).get("total")
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _format_inr(value: Decimal) -> str:
    return "Rs " + f"{int(value):,}" if value == value.to_integral() else "Rs " + f"{value:,.2f}"


@staff_member_required
def admin_dashboard_realtime(request):
    return JsonResponse(build_admin_dashboard_realtime_payload())


def build_admin_dashboard_realtime_payload() -> dict:
    User = get_user_model()
    now = timezone.now()

    try:
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
    except Exception:
        total_users = 0
        active_users = 0

    online_users = _count("enterprise_control.DeviceSession", is_active=True)
    devices = _count("enterprise_control.DeviceSession")
    active_pos = _count("enterprise_control.DeviceSession", is_active=True, platform__icontains="pos")
    selfcheckout = _count("selfcheckout.KioskDevice")
    companies = _count("core_settings.CompanySettings") or _count("apps.platform.core.Company")
    subscriptions = _count("billing.Subscription")
    orders = _count("storefront.StoreOrder") or _count("commerce.Order")
    revenue = _sum("storefront.StoreOrder", "total_amount", status__in=["accepted", "packed", "shipped", "delivered"])

    activities = []
    try:
        for entry in LogEntry.objects.select_related("user", "content_type").order_by("-action_time")[:8]:
            activities.append(
                {
                    "action": str(entry.object_repr or entry.get_change_message() or "Admin activity")[:80],
                    "actor": getattr(entry.user, "email", "") or getattr(entry.user, "username", "") or "Admin",
                    "when": entry.action_time.strftime("%d %b, %I:%M %p"),
                }
            )
    except Exception:
        activities = []

    return {
        "status": "live",
        "server_time": now.isoformat(),
        "kpis": {
            "total_users": {"value": total_users, "formatted": f"{total_users:,}"},
            "active_users": {"value": active_users, "formatted": f"{active_users:,}"},
            "online_users": {"value": online_users, "formatted": f"{online_users:,}"},
            "companies": {"value": companies, "formatted": f"{companies:,}"},
            "revenue": {"value": str(revenue), "formatted": _format_inr(revenue)},
            "subscriptions": {"value": subscriptions, "formatted": f"{subscriptions:,}"},
            "orders": {"value": orders, "formatted": f"{orders:,}"},
            "devices": {"value": devices, "formatted": f"{devices:,}"},
            "active_pos": {"value": active_pos, "formatted": f"{active_pos:,}"},
            "selfcheckout": {"value": selfcheckout, "formatted": f"{selfcheckout:,}"},
            "api_usage": {"value": 0, "formatted": "Ready"},
        },
        "activities": activities,
        "realtime": {
            "dashboard_channel": "ws/enterprise/dashboard/",
            "permissions_channel": "ws/enterprise/permissions/",
            "modules_channel": "ws/enterprise/modules/",
        },
    }
