import time
import uuid

from apps.platform.core.models import ObservabilityEvent


class RequestTracingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.trace_id = trace_id
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response["X-Trace-Id"] = trace_id
        self._record(request, response, duration_ms, trace_id)
        return response

    def _record(self, request, response, duration_ms, trace_id):
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return
        try:
            ObservabilityEvent.objects.create(
                tenant=getattr(request, "identity_tenant", None),
                event_type=ObservabilityEvent.EventType.REQUEST,
                trace_id=trace_id,
                name=f"{request.method} {request.path[:180]}",
                duration_ms=duration_ms,
                severity="warning" if duration_ms >= 1500 or response.status_code >= 500 else "info",
                context={"status_code": response.status_code, "user_id": getattr(getattr(request, "user", None), "id", None)},
            )
        except Exception:
            return

