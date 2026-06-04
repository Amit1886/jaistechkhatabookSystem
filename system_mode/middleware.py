from django.utils.deprecation import MiddlewareMixin

from .services import build_request_mode_context


class SystemModeMiddleware(MiddlewareMixin):
    def process_request(self, request):
        context = build_request_mode_context(request)
        request.system_mode_context = context
        request.system_mode = context.get("current_mode")
        request.resolved_system_mode = context.get("resolved_mode")

    def process_response(self, request, response):
        context = getattr(request, "system_mode_context", None)
        if context:
            response["X-System-Mode"] = str(context.get("current_mode", "DESKTOP"))
            response["X-Resolved-Mode"] = str(context.get("resolved_mode", "DESKTOP"))
            response["X-System-Mode-Locked"] = "1" if context.get("is_locked") else "0"
        return response
