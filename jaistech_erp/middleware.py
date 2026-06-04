from __future__ import annotations

import traceback

from django.utils import timezone


def _solution_for_exception(exc: Exception, request) -> tuple[str, str]:
    name = exc.__class__.__name__
    message = str(exc)
    path = getattr(request, "path", "")
    if "Authorization" in message or "authentication" in message.lower():
        return (
            "Request authentication failed or token was missing/invalid.",
            "Login again, refresh JWT token, and ensure the API client sends `Authorization: Bearer <access>`.",
        )
    if "RenderFlex" in message or "overflow" in message.lower():
        return (
            "Flutter screen layout overflowed on a small device.",
            "Wrap the overflowing row in Flexible/Expanded, hide non-essential controls on compact width, or use horizontal scrolling.",
        )
    if "/api/app/invoices" in path:
        return (
            "Invoice API failed while loading invoice data.",
            "Check invoice/order relations and avoid calling DRF-decorated views from another DRF view. Use a plain helper function.",
        )
    return (
        f"{name}: {message[:300]}",
        "Open this error, inspect traceback and endpoint, then apply the recommended module-level fix. If repeated, add validation and a safe JSON fallback response.",
    )


class AdminErrorNotificationMiddleware:
    """
    Stores uncaught backend errors in Django Admin as System Error Q&A items.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            self._record(request, exc)
            raise

    def _record(self, request, exc: Exception) -> None:
        try:
            from .models import SystemErrorLog

            root_cause, recommended_fix = _solution_for_exception(exc, request)
            endpoint = getattr(request, "path", "")
            method = getattr(request, "method", "")
            title = f"{exc.__class__.__name__} on {method} {endpoint}"[:180]
            existing = SystemErrorLog.objects.filter(
                title=title,
                endpoint=endpoint,
                status="open",
            ).first()
            if existing:
                existing.occurrences += 1
                existing.exception = repr(exc)
                existing.traceback = traceback.format_exc()
                existing.last_seen_at = timezone.now()
                existing.save(update_fields=["occurrences", "exception", "traceback", "last_seen_at", "updated_at"])
                return
            SystemErrorLog.objects.create(
                title=title,
                severity="critical",
                source="middleware",
                endpoint=endpoint,
                method=method,
                status_code=500,
                user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                problem=f"Unhandled backend error on {method} {endpoint}.",
                root_cause=root_cause,
                recommended_fix=recommended_fix,
                exception=repr(exc),
                traceback=traceback.format_exc(),
            )
        except Exception:
            pass
