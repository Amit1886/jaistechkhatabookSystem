from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from distribution.models import (
    AppPlatform,
    AppVersion,
    DeviceRegistry,
    FeatureRegistry,
    Industry,
    ModuleRegistry,
    RemoteConfig,
    SoftwareBuild,
)


def _public_build_url(request, build: SoftwareBuild):
    if build.external_url:
        return build.external_url
    if build.web_launch_url:
        return build.web_launch_url
    if build.pwa_url:
        return build.pwa_url
    if build.installer_file:
        return request.build_absolute_uri(f"/downloads/file/{build.slug}/")
    return ""


def get_industry(slug: str | None):
    if not slug:
        return None
    return Industry.objects.filter(slug=slug, is_active=True).first()


def build_download_catalog(request, *, industry_slug: str | None = None, user=None):
    industry = get_industry(industry_slug)
    industries = Industry.objects.filter(is_active=True).order_by("sort_order", "name")
    builds = SoftwareBuild.objects.filter(is_published=True).prefetch_related("industries", "platform", "modules")
    if industry:
        builds = builds.filter(Q(industries=industry) | Q(industries__isnull=True)).distinct()
    rows = []
    for build in builds.order_by("sort_order", "title"):
        rows.append(
            {
                "id": build.id,
                "title": build.title,
                "slug": build.slug,
                "build_type": build.build_type,
                "version": build.version,
                "icon": build.platform.icon if build.platform else "",
                "download_url": _public_build_url(request, build),
                "web_launch_url": build.web_launch_url,
                "pwa_url": build.pwa_url,
                "play_store_url": build.play_store_url,
                "app_store_url": build.app_store_url,
                "release_notes": build.release_notes,
                "sha256": build.sha256,
                "requires_login": build.requires_login,
                "industries": [i.slug for i in build.industries.all()],
                "modules": [m.slug for m in build.modules.all()],
            }
        )
    return {
        "industries": list(industries.values("slug", "name", "icon", "description")),
        "active_industry": industry.slug if industry else "",
        "builds": rows,
    }


def resolve_live_config(*, user=None, industry_slug: str = "", device_uid: str = "", platform_code: str = "", app_version: str = "", request=None):
    industry = get_industry(industry_slug)
    platform = AppPlatform.objects.filter(code=platform_code, is_active=True).first() if platform_code else None

    if device_uid:
        device, _ = DeviceRegistry.objects.get_or_create(
            device_uid=device_uid,
            defaults={
                "owner": user if getattr(user, "is_authenticated", False) else None,
                "industry": industry,
                "platform": platform,
                "device_type": platform.platform_type if platform else DeviceRegistry.DeviceType.WEB,
                "app_version": app_version or "",
            },
        )
        device.industry = industry or device.industry
        device.platform = platform or device.platform
        device.owner = user if getattr(user, "is_authenticated", False) else device.owner
        device.touch(ip_address=(request.META.get("REMOTE_ADDR") if request else None), app_version=app_version or device.app_version)

    modules = ModuleRegistry.objects.filter(is_enabled=True).prefetch_related("supported_platforms", "features", "industries")
    features = FeatureRegistry.objects.filter(is_enabled=True).prefetch_related("supported_platforms", "industries")
    builds = SoftwareBuild.objects.filter(is_published=True).prefetch_related("industries")

    if industry:
        modules = modules.filter(Q(industries=industry) | Q(industries__isnull=True)).distinct()
        features = features.filter(Q(industries=industry) | Q(industries__isnull=True)).distinct()
        builds = builds.filter(Q(industries=industry) | Q(industries__isnull=True)).distinct()
    if platform:
        modules = modules.filter(Q(supported_platforms=platform) | Q(supported_platforms__isnull=True)).distinct()
        features = features.filter(Q(supported_platforms=platform) | Q(supported_platforms__isnull=True)).distinct()
        builds = builds.filter(Q(platform=platform) | Q(platform__isnull=True)).distinct()

    remote_q = RemoteConfig.objects.filter(is_active=True).filter(
        Q(scope=RemoteConfig.Scope.GLOBAL)
        | Q(scope=RemoteConfig.Scope.INDUSTRY, industry=industry)
        | Q(scope=RemoteConfig.Scope.USER, user=user if getattr(user, "is_authenticated", False) else None)
        | Q(scope=RemoteConfig.Scope.DEVICE, device_uid=device_uid)
    )
    configs = {cfg.key: cfg.payload for cfg in remote_q.order_by("scope", "updated_at")}
    latest_config_version = max([cfg.version for cfg in remote_q] or [1])

    current = AppVersion.objects.filter(platform=platform, is_current=True).order_by("-updated_at").first() if platform else None
    return {
        "server_time": timezone.now().isoformat(),
        "config_version": latest_config_version,
        "platform": platform_code,
        "industry": industry.slug if industry else "",
        "update": {
            "current_version": current.version if current else "",
            "min_supported_version": current.min_supported_version if current else "",
            "force_update": current.force_update if current else False,
            "message": current.update_message if current else "",
        },
        "remote_config": configs,
        "features": [
            {
                "slug": f.slug,
                "name": f.name,
                "icon": f.icon,
                "version": f.version,
                "rollout_status": f.rollout_status,
                "permissions": f.permissions,
                "payload": f.remote_payload,
            }
            for f in features.order_by("name")
        ],
        "modules": [
            {
                "slug": m.slug,
                "name": m.name,
                "module_type": m.module_type,
                "icon": m.icon,
                "route_path": m.route_path,
                "api_endpoint": m.api_endpoint,
                "component_key": m.component_key,
                "version": m.version,
                "lazy_load": m.lazy_load,
                "permissions": m.permissions,
                "ui_schema": m.ui_schema,
                "payload": m.remote_payload,
            }
            for m in modules.order_by("sort_order", "name")
        ],
        "downloads": [
            {
                "slug": b.slug,
                "title": b.title,
                "build_type": b.build_type,
                "version": b.version,
                "sha256": b.sha256,
                "web_launch_url": b.web_launch_url,
                "pwa_url": b.pwa_url,
                "play_store_url": b.play_store_url,
                "app_store_url": b.app_store_url,
            }
            for b in builds.order_by("sort_order", "title")
        ],
    }


def publish_distribution_sync(event_type: str, payload: dict):
    try:
        from realtime.services.publisher import publish_event

        publish_event("distribution", event_type, payload)
    except Exception:
        pass

