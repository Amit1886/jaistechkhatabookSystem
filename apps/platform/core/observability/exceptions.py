from rest_framework.views import exception_handler


def enterprise_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request") if context else None
    if response is not None:
        response.data = {
            "error": True,
            "status_code": response.status_code,
            "detail": response.data,
            "trace_id": getattr(request, "trace_id", ""),
        }
    return response

