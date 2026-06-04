import os
from django.apps import apps
from django.conf import settings
from .models import UISettings, CompanySettings

def global_settings(request):
    request_host = ""
    try:
        request_host = (request.get_host() or "").split(":")[0].strip().lower()
    except Exception:
        request_host = ""
    is_local_request = request_host in {"127.0.0.1", "localhost", "0.0.0.0"}
    is_local_base_url = bool(getattr(settings, "IS_LOCAL_BASE_URL", False)) or is_local_request
    running_runserver = bool(getattr(settings, "RUNNING_RUNSERVER", False))
    desktop_mode = bool(getattr(settings, "DESKTOP_MODE", False))

    # When running locally (or desktop), prefer local vendor assets over CDN so UI works offline.
    use_local_vendor_assets = bool(desktop_mode or running_runserver or is_local_base_url)

    user = getattr(request, "user", None)
    profile = None
    if getattr(user, "is_authenticated", False):
        profile = getattr(user, "khata_profile", None) or getattr(user, "profile", None)
    role_label = "Admin" if getattr(user, "is_superuser", False) else "Staff" if getattr(user, "is_staff", False) else "User"
    business_name = (
        getattr(profile, "business_name", "")
        or getattr(CompanySettings.objects.first(), "company_name", "")
        or "Main Branch"
    )

    return {
        "ui": UISettings.objects.first(),
        "company": CompanySettings.objects.first(),
        "demo_user_display": {
            "name": (getattr(user, "username", "") or "Demotest3") if getattr(user, "is_authenticated", False) else "Demotest3",
            "role": role_label,
            "business_name": business_name,
            "last_login": getattr(user, "last_login", None),
            "online": bool(getattr(user, "is_authenticated", False)),
        },
        "desktop_mode": desktop_mode,
        "desktop_app_version": (getattr(settings, "DESKTOP_APP_VERSION", "") or os.getenv("DESKTOP_APP_VERSION") or "0.0.0").strip(),
        "use_local_vendor_assets": use_local_vendor_assets,
        "is_local_base_url": is_local_base_url,
        "google_login_enabled": apps.is_installed("allauth.socialaccount.providers.google"),
        "google_maps_api_key": (getattr(settings, "GOOGLE_MAPS_API_KEY", "") or "").strip(),
    }

def ui_settings(request):
    return {
        "ui": UISettings.objects.first()
    }
