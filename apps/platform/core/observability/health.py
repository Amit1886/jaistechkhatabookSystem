from django.db import connection
from django.http import JsonResponse


def enterprise_health(request):
    checks = {"database": "unknown", "cache": "unknown", "event_bus": "unknown"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"
    try:
        from django.core.cache import cache

        cache.set("enterprise_health", "ok", 10)
        checks["cache"] = cache.get("enterprise_health") or "failed"
    except Exception:
        checks["cache"] = "failed"
    try:
        from event_bus.models import EventOutbox

        checks["event_bus"] = {"pending": EventOutbox.objects.filter(status="pending").count()}
    except Exception:
        checks["event_bus"] = "failed"
    status = 200 if checks["database"] == "ok" else 503
    return JsonResponse({"ok": status == 200, "checks": checks}, status=status)

