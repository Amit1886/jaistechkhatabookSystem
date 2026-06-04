from __future__ import annotations

from typing import Any

from vendors.models import MarketplaceApp, Vendor, VendorAppInstall


BUILTIN_APP_CODES = [
    "lead_capture_popup",
    "announcement_bar",
    "whatsapp_chat",
    "social_proof_popup",
]


def ensure_builtin_apps_exist():
    """
    Idempotent seeding for builtin apps (Phase A).
    """

    defs = [
        {
            "code": "lead_capture_popup",
            "name": "Lead capture popup",
            "category": MarketplaceApp.Category.MARKETING,
            "short_description": "Collect leads from your storefront with a popup form.",
            "icon": "",
            "rating": 4.7,
            "default_config": {"enabled": False, "delay_seconds": 7, "title": "Get offers on WhatsApp", "cta": "Get updates"},
        },
        {
            "code": "announcement_bar",
            "name": "Announcement bar",
            "category": MarketplaceApp.Category.MARKETING,
            "short_description": "Show a top announcement (free shipping, offers).",
            "icon": "",
            "rating": 4.8,
            "default_config": {"enabled": False, "text": "Free delivery on orders above ₹499", "style": "dark"},
        },
        {
            "code": "whatsapp_chat",
            "name": "WhatsApp chat button",
            "category": MarketplaceApp.Category.SUPPORT,
            "short_description": "Floating WhatsApp button for quick customer support.",
            "icon": "",
            "rating": 4.9,
            "default_config": {"enabled": False, "phone": "", "message": "Hi, I need help with my order."},
        },
        {
            "code": "social_proof_popup",
            "name": "Social proof popup",
            "category": MarketplaceApp.Category.SALES,
            "short_description": "Show recent purchase popups to boost conversions (demo).",
            "icon": "",
            "rating": 4.6,
            "default_config": {"enabled": False, "interval_seconds": 12},
        },
    ]

    for d in defs:
        MarketplaceApp.objects.get_or_create(code=d["code"], defaults=d)


def list_marketplace_apps() -> list[MarketplaceApp]:
    ensure_builtin_apps_exist()
    return list(MarketplaceApp.objects.filter(is_active=True).order_by("category", "name"))


def get_vendor_installs_map(vendor: Vendor) -> dict[str, VendorAppInstall]:
    installs = VendorAppInstall.objects.select_related("app").filter(vendor=vendor, app__is_active=True)
    return {i.app.code: i for i in installs}


def install_app(*, vendor: Vendor, app: MarketplaceApp) -> VendorAppInstall:
    obj, created = VendorAppInstall.objects.get_or_create(vendor=vendor, app=app)
    if created:
        obj.is_installed = True
        obj.is_enabled = bool((app.default_config or {}).get("enabled", True))
        obj.config = dict(app.default_config or {})
        obj.save()
    else:
        if not obj.is_installed:
            obj.is_installed = True
            obj.save(update_fields=["is_installed", "updated_at"])
    return obj


def uninstall_app(*, vendor: Vendor, app: MarketplaceApp) -> None:
    VendorAppInstall.objects.filter(vendor=vendor, app=app).update(is_installed=False, is_enabled=False)


def update_app_config(*, install: VendorAppInstall, config_updates: dict[str, Any]):
    blob = dict(install.config or {})
    blob.update({k: v for k, v in (config_updates or {}).items()})
    install.config = blob
    install.save(update_fields=["config", "updated_at"])


def enabled_apps_for_storefront(vendor: Vendor) -> dict[str, dict]:
    """
    Returns `{code: config}` for enabled + installed apps.
    """

    ensure_builtin_apps_exist()
    installs = VendorAppInstall.objects.select_related("app").filter(vendor=vendor, is_installed=True, is_enabled=True, app__is_active=True)
    out = {}
    for i in installs:
        out[i.app.code] = dict(i.config or {})
    return out

