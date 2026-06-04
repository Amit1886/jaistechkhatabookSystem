import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import UntypedToken

from fastapi_app.auth.token_utils import decode_token
from fastapi_app.routers import mobile as fastapi_mobile


def _bearer_user(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None, JsonResponse({"detail": "missing_token"}, status=401)
    token = header[len(prefix):].strip()

    try:
        payload = decode_token(token)
        if "type" not in payload:
            raise ValueError("not_fastapi_token")
        if payload.get("type") != "access":
            return None, JsonResponse({"detail": "access_token_required"}, status=401)
        user = get_user_model().objects.filter(pk=payload.get("sub"), is_active=True).first()
        if not user:
            return None, JsonResponse({"detail": "user_not_found"}, status=401)
        return user, None
    except Exception:
        pass

    try:
        validated = UntypedToken(token)
        user_id = validated.get(api_settings.USER_ID_CLAIM)
        user = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: user_id}, is_active=True).first()
        if user:
            return user, None
    except Exception:
        pass
    return None, JsonResponse({"detail": "invalid_token"}, status=401)


def _json(data):
    return JsonResponse(json.loads(json.dumps(data, default=str)), safe=isinstance(data, dict))


@csrf_exempt
def current_user(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.current_user_profile(platform=request.GET.get("platform", "app"), user=user))


@csrf_exempt
def app_config(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.app_config(platform=request.GET.get("platform", "app"), user=user))


@csrf_exempt
def modules(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.modules(platform=request.GET.get("platform", "app"), user=user))


@csrf_exempt
def dashboard_buttons(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.dashboard_buttons(platform=request.GET.get("platform", "app"), user=user))


@csrf_exempt
def menu(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.menu(platform=request.GET.get("platform", "app"), user=user))


@csrf_exempt
def bootstrap(request):
    user, error = _bearer_user(request)
    if error:
        return error
    platform = request.GET.get("platform", "app")
    payload = fastapi_mobile.bootstrap(platform=platform, user=user)
    try:
        from fastapi_app.routers.system import _dashboard_config, _live_data, _report_payload

        payload["live_data"] = _live_data(user)
        payload["dashboard_config"] = _dashboard_config(user)
        payload["reports"] = _report_payload(user)
    except Exception:
        payload.setdefault("live_data", {})
    return _json(payload)


@csrf_exempt
def screen_metadata(request, module):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(fastapi_mobile.screen_metadata(module=module, user=user))


@csrf_exempt
def auth_me(request):
    user, error = _bearer_user(request)
    if error:
        return error
    profile = fastapi_mobile.current_user_profile(platform=request.GET.get("platform", "app"), user=user)
    return _json({"authenticated": True, "user": profile.get("user", {}), **profile})


@csrf_exempt
def features(request):
    user, error = _bearer_user(request)
    if error:
        return error
    profile = fastapi_mobile.current_user_profile(platform=request.GET.get("platform", "app"), user=user)
    config = fastapi_mobile.app_config(platform=request.GET.get("platform", "app"), user=user)
    return _json(
        {
            "enabled_features": profile.get("enabled_features", []),
            "enabled_modules": profile.get("enabled_modules", []),
            "plan": profile.get("subscription_plan", {}),
            "buttons": config.get("buttons", []),
        }
    )


@csrf_exempt
def realtime(request):
    user, error = _bearer_user(request)
    if error:
        return error
    return _json(
        {
            "permission_channel": "ws/enterprise/permissions/",
            "dashboard_channel": "ws/enterprise/dashboard/",
            "module_channel": "ws/enterprise/modules/",
            "polling": {
                "dashboard": "/superadmin/api/dashboard-realtime/",
                "bootstrap": "/api/mobile/bootstrap/",
            },
            "user_id": user.pk,
        }
    )
