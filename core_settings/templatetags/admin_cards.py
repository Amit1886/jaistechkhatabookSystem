from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django import template
from django.apps import apps
from django.urls import NoReverseMatch, reverse


register = template.Library()


BOOL_STATUS_FIELDS: Tuple[str, ...] = ("is_active", "active", "enabled", "is_enabled", "status")


def _get_model(app_label: str, object_name: str):
    try:
        return apps.get_model(app_label, object_name)
    except Exception:
        return None


def _changelist_url(app_label: str, model_name: str) -> Optional[str]:
    try:
        return reverse(f"admin:{app_label}_{model_name}_changelist")
    except NoReverseMatch:
        return None


def _safe_count(qs) -> int:
    try:
        return int(qs.count())
    except Exception:
        return 0


def _status_counts(model) -> Dict[str, Any]:
    """
    Compute total + (active/inactive) when a common boolean status field exists.
    """
    if not model:
        return {"total": None, "field": None, "active": None, "inactive": None}
    try:
        qs = model.objects.all()
    except Exception:
        return {"total": None, "field": None, "active": None, "inactive": None}

    total = _safe_count(qs)

    field_name = None
    for f in BOOL_STATUS_FIELDS:
        try:
            field = model._meta.get_field(f)  # type: ignore[attr-defined]
            if getattr(field, "get_internal_type", lambda: "")() == "BooleanField":
                field_name = f
                break
        except Exception:
            continue

    if not field_name:
        return {"total": total, "field": None, "active": None, "inactive": None}

    active = _safe_count(qs.filter(**{field_name: True}))
    inactive = max(total - active, 0)
    return {"total": total, "field": field_name, "active": active, "inactive": inactive}


@register.simple_tag(takes_context=True)
def admin_dashboard_cards(context):
    """
    Build a "card" view for the admin index, using the existing `app_list`.

    - Automatically includes any newly registered admin model.
    - Adds optional Active/Inactive quick links for models that have a boolean status field.
    """
    app_list = context.get("app_list") or []
    cards: List[Dict[str, Any]] = []

    for app in app_list:
        app_label = app.get("app_label") or ""
        models = []
        for m in app.get("models") or []:
            object_name = m.get("object_name") or ""
            model_class = _get_model(app_label, object_name)
            counts = _status_counts(model_class)

            changelist = m.get("admin_url") or _changelist_url(app_label, (m.get("model") or ""))
            add_url = m.get("add_url")

            status_field = counts.get("field")
            active_url = None
            inactive_url = None
            if changelist and status_field:
                active_url = f"{changelist}?{status_field}__exact=1"
                inactive_url = f"{changelist}?{status_field}__exact=0"

            models.append(
                {
                    "name": m.get("name"),
                    "object_name": object_name,
                    "admin_url": changelist,
                    "add_url": add_url,
                    "total": counts.get("total"),
                    "status_field": status_field,
                    "active": counts.get("active"),
                    "inactive": counts.get("inactive"),
                    "active_url": active_url,
                    "inactive_url": inactive_url,
                }
            )

        cards.append(
            {
                "name": app.get("name"),
                "app_label": app_label,
                "app_url": app.get("app_url"),
                "models": models,
            }
        )

    return {"apps": cards}

