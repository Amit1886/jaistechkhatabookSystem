from __future__ import annotations

import os
from typing import Any

from django.conf import settings
from django.core.cache import cache


DEFAULT_PUBLIC_SETTINGS = {
    "app_name": "Billentra",
    "api_prefix": "/fastapi",
    "metadata_url": "/fastapi/metadata/models",
    "crud_url": "/fastapi/crud",
    "auth_url": "/fastapi/auth",
    "offline_pos_enabled": True,
    "multi_company_enabled": True,
}


class SettingsService:
    cache_key = "enterprise:public_settings:v1"

    def get_public_settings(self, *, request=None) -> dict[str, Any]:
        cached = cache.get(self.cache_key)
        if cached:
            return cached
        base_url = self._base_url(request)
        payload = {
            **DEFAULT_PUBLIC_SETTINGS,
            "api_base_url": f"{base_url}/fastapi",
            "django_base_url": base_url,
            "debug": bool(getattr(settings, "DEBUG", False)),
            "desktop_mode": bool(getattr(settings, "DESKTOP_MODE", False)),
            "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
            "branding": {
                "name": "Billentra",
                "logo": "/static/img/billentra-logo.png",
                "favicon": "/static/img/billentra-favicon.ico",
            },
        }
        payload.update(self._db_public_settings())
        cache.set(self.cache_key, payload, 300)
        return payload

    def mobile_auto_config(self, *, request=None) -> dict[str, Any]:
        public = self.get_public_settings(request=request)
        return {
            "settings": public,
            "features": {
                "dynamic_forms": True,
                "dynamic_tables": True,
                "offline_queue": True,
                "barcode_scanner": True,
                "thermal_printer": True,
                "realtime": True,
            },
            "sync": {
                "pull_metadata": "/fastapi/metadata/models",
                "crud_base": "/fastapi/crud",
                "conflict_policy": "server_timestamp_wins",
            },
        }

    @staticmethod
    def _base_url(request=None) -> str:
        configured = (os.getenv("BASE_URL") or "").strip().rstrip("/")
        if configured:
            return configured
        if request is not None:
            try:
                return str(request.base_url).rstrip("/")
            except Exception:
                pass
        return "http://127.0.0.1:8080"

    @staticmethod
    def _db_public_settings() -> dict[str, Any]:
        try:
            from core.models import EnterpriseSetting

            rows = EnterpriseSetting.objects.filter(is_active=True, scope__in=["public", "mobile"])
            return {row.key: row.resolved_value() for row in rows}
        except Exception:
            return {}


settings_service = SettingsService()
