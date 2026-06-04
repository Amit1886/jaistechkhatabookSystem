from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.apps import apps
from django.db import models


SENSITIVE_FIELD_NAMES = {
    "password",
    "secret",
    "token",
    "api_key",
    "private_key",
    "access_token",
    "refresh_token",
}


def model_key(model: type[models.Model]) -> str:
    return f"{model._meta.app_label}.{model._meta.model_name}"


def resolve_model(key: str) -> type[models.Model]:
    try:
        app_label, model_name = key.split(".", 1)
    except ValueError as exc:
        raise LookupError("Model key must be '<app_label>.<model_name>'.") from exc
    model = apps.get_model(app_label, model_name)
    if model is None:
        raise LookupError(f"Unknown model: {key}")
    return model


def _is_sensitive(field: models.Field) -> bool:
    name = field.name.lower()
    return any(part in name for part in SENSITIVE_FIELD_NAMES)


def _field_kind(field: models.Field) -> str:
    if field.many_to_many:
        return "many_to_many"
    if field.one_to_many:
        return "one_to_many"
    if field.many_to_one:
        return "foreign_key"
    if field.one_to_one:
        return "one_to_one"
    if isinstance(field, (models.IntegerField, models.AutoField, models.BigAutoField)):
        return "integer"
    if isinstance(field, (models.FloatField, models.DecimalField)):
        return "number"
    if isinstance(field, models.BooleanField):
        return "boolean"
    if isinstance(field, (models.DateField, models.DateTimeField, models.TimeField)):
        return "date"
    if isinstance(field, models.JSONField):
        return "json"
    if isinstance(field, models.TextField):
        return "text"
    if isinstance(field, (models.EmailField, models.URLField, models.SlugField, models.CharField)):
        return "string"
    if isinstance(field, models.FileField):
        return "file"
    return field.get_internal_type()


def _field_metadata(field: models.Field) -> dict[str, Any]:
    related_model = getattr(field, "related_model", None)
    validators = [
        validator.__class__.__name__
        for validator in getattr(field, "validators", [])
    ]
    return {
        "name": field.name,
        "label": str(getattr(field, "verbose_name", field.name)).title(),
        "type": _field_kind(field),
        "django_type": field.get_internal_type(),
        "required": not getattr(field, "blank", False)
        and not getattr(field, "null", False)
        and not getattr(field, "primary_key", False),
        "read_only": bool(getattr(field, "primary_key", False) or getattr(field, "auto_created", False)),
        "primary_key": bool(getattr(field, "primary_key", False)),
        "unique": bool(getattr(field, "unique", False)),
        "indexed": bool(getattr(field, "db_index", False)),
        "max_length": getattr(field, "max_length", None),
        "choices": [
            {"value": value, "label": str(label)}
            for value, label in getattr(field, "choices", []) or []
        ],
        "relation": model_key(related_model) if related_model else None,
        "validators": validators,
        "sensitive": _is_sensitive(field),
        "mobile_widget": mobile_widget_for(field),
        "filterable": not _is_sensitive(field) and _field_kind(field) in {"string", "integer", "number", "boolean", "date", "foreign_key"},
        "searchable": not _is_sensitive(field) and _field_kind(field) in {"string", "text"},
    }


def mobile_widget_for(field: models.Field) -> str:
    kind = _field_kind(field)
    if getattr(field, "choices", None):
        return "select"
    return {
        "string": "text",
        "text": "textarea",
        "integer": "number",
        "number": "decimal",
        "boolean": "switch",
        "date": "date_picker",
        "foreign_key": "relation_dropdown",
        "many_to_many": "multi_select",
        "json": "json_editor",
        "file": "file_picker",
    }.get(kind, "text")


def model_metadata(model: type[models.Model]) -> dict[str, Any]:
    fields = [
        _field_metadata(field)
        for field in model._meta.get_fields()
        if not getattr(field, "one_to_many", False) and not getattr(field, "auto_created", False)
    ]
    search_fields = [field["name"] for field in fields if field["searchable"]]
    filter_fields = [field["name"] for field in fields if field["filterable"]]
    return {
        "key": model_key(model),
        "app_label": model._meta.app_label,
        "model_name": model._meta.model_name,
        "object_name": model._meta.object_name,
        "label": str(model._meta.verbose_name).title(),
        "label_plural": str(model._meta.verbose_name_plural).title(),
        "db_table": model._meta.db_table,
        "ordering": list(model._meta.ordering or []),
        "fields": fields,
        "search_fields": search_fields,
        "filter_fields": filter_fields,
        "permissions": {
            "view": f"{model._meta.app_label}.view_{model._meta.model_name}",
            "add": f"{model._meta.app_label}.add_{model._meta.model_name}",
            "change": f"{model._meta.app_label}.change_{model._meta.model_name}",
            "delete": f"{model._meta.app_label}.delete_{model._meta.model_name}",
        },
        "api": {
            "base": f"/fastapi/crud/{model_key(model)}",
            "list": f"/fastapi/crud/{model_key(model)}/",
            "detail": f"/fastapi/crud/{model_key(model)}/{{pk}}",
            "schemas": f"/fastapi/schemas/{model_key(model)}",
        },
        "mobile": {
            "screen_key": model_key(model).replace(".", "_"),
            "list_title": str(model._meta.verbose_name_plural).title(),
            "form_title": str(model._meta.verbose_name).title(),
        },
    }


@lru_cache(maxsize=1)
def scan_models() -> list[dict[str, Any]]:
    return [
        model_metadata(model)
        for model in apps.get_models()
        if not model._meta.abstract and not model._meta.proxy
    ]


def clear_metadata_cache() -> None:
    scan_models.cache_clear()
