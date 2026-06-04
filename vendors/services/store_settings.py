from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VendorSettingField:
    key: str
    label: str
    section: str


# A minimal Shopify-inspired registry (backend-only).
# These keys can be posted from any future UI without changing DB schema.
SHOPIFY_LIKE_FIELDS: list[VendorSettingField] = [
    VendorSettingField("store_contact_name", "Store contact name", "general"),
    VendorSettingField("store_contact_email", "Store contact email", "general"),
    VendorSettingField("store_contact_phone", "Store contact phone", "general"),
    VendorSettingField("backup_region", "Backup region", "general"),
    VendorSettingField("unit_system", "Unit system", "general"),  # metric/imperial
    VendorSettingField("default_weight_unit", "Default weight unit", "general"),  # kg/g/lb/oz
    VendorSettingField("currency_display", "Currency display", "general"),
    VendorSettingField("customer_accounts", "Customer accounts", "checkout"),  # required/optional/off
    VendorSettingField("guest_checkout_enabled", "Guest checkout enabled", "checkout"),
    VendorSettingField("tax_included_in_prices", "Prices include tax", "tax"),
]


def get_settings_blob(settings_obj) -> dict:
    try:
        blob = getattr(settings_obj, "settings_json", None) or {}
        return blob if isinstance(blob, dict) else {}
    except Exception:
        return {}


def set_settings_blob(settings_obj, blob: dict) -> None:
    settings_obj.settings_json = blob if isinstance(blob, dict) else {}


def update_settings_from_post(settings_obj, post) -> bool:
    """
    Update `VendorStoreSettings.settings_json` from POSTed values.
    Returns True if any changes were made.
    """
    blob = get_settings_blob(settings_obj)
    changed = False

    allowed = {f.key for f in SHOPIFY_LIKE_FIELDS}
    for key in allowed:
        if key not in post:
            continue
        raw = post.get(key)
        val = (raw or "").strip() if isinstance(raw, str) else raw
        if blob.get(key) != val:
            blob[key] = val
            changed = True

    if changed:
        set_settings_blob(settings_obj, blob)
    return changed


def build_settings_summary(settings_obj) -> dict:
    """
    Returns a safe summary used for dashboards (no secrets).
    """
    blob = get_settings_blob(settings_obj)
    return {
        "unit_system": (blob.get("unit_system") or "").strip() or "metric",
        "default_weight_unit": (blob.get("default_weight_unit") or "").strip() or "kg",
        "backup_region": (blob.get("backup_region") or "").strip() or (getattr(settings_obj, "country", "") or "India"),
        "customer_accounts": (blob.get("customer_accounts") or "").strip() or "optional",
        "guest_checkout_enabled": bool(blob.get("guest_checkout_enabled") in {True, "true", "1", 1, "yes", "on"}),
    }

