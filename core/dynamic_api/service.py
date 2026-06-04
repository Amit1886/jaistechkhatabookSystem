from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.base import File
from django.db import models, transaction
from django.forms.models import model_to_dict

from core.metadata.scanner import model_metadata


class CRUDService:
    """Model-agnostic CRUD service.

    The service owns ORM logic so FastAPI handlers stay transport-focused.
    """

    def __init__(self, model: type[models.Model]):
        self.model = model
        self.meta = model_metadata(model)

    def base_queryset(self):
        return self.model._default_manager.all()

    def list(
        self,
        *,
        user,
        filters: dict[str, Any] | None = None,
        search: str = "",
        ordering: str = "",
        limit: int = 50,
        offset: int = 0,
        company_id: str = "",
    ) -> dict[str, Any]:
        qs = self.apply_company_scope(self.base_queryset(), company_id=company_id)
        qs = self.apply_filters(qs, filters or {})
        qs = self.apply_search(qs, search)
        qs = self.apply_ordering(qs, ordering)
        total = qs.count()
        rows = list(qs[offset : offset + limit])
        return {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": [self.serialize(obj) for obj in rows],
        }

    def get(self, pk: str):
        return self.base_queryset().get(pk=pk)

    @transaction.atomic
    def create(self, *, data: dict[str, Any], user=None):
        clean = self.clean_write_payload(data)
        obj = self.model(**clean)
        obj.full_clean(exclude=None)
        obj.save()
        return obj

    @transaction.atomic
    def update(self, *, pk: str, data: dict[str, Any], partial: bool = True, user=None):
        obj = self.get(pk)
        clean = self.clean_write_payload(data)
        for key, value in clean.items():
            setattr(obj, key, value)
        obj.full_clean(exclude=None if not partial else [])
        obj.save()
        return obj

    @transaction.atomic
    def delete(self, *, pk: str) -> dict[str, Any]:
        obj = self.get(pk)
        obj.delete()
        return {"deleted": True, "pk": pk}

    def clean_write_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            field["name"]
            for field in self.meta["fields"]
            if not field["read_only"] and not field["sensitive"]
        }
        clean: dict[str, Any] = {}
        for key, value in (data or {}).items():
            if key not in allowed:
                continue
            try:
                field = self.model._meta.get_field(key)
            except FieldDoesNotExist:
                continue
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                clean[f"{key}_id"] = value
            else:
                clean[key] = value
        return clean

    def apply_filters(self, qs, filters: dict[str, Any]):
        allowed = set(self.meta["filter_fields"])
        for key, value in filters.items():
            if key in allowed and value not in ("", None):
                qs = qs.filter(**{key: value})
        return qs

    def apply_search(self, qs, search: str):
        search = (search or "").strip()
        if not search:
            return qs
        query = models.Q()
        for field in self.meta["search_fields"][:8]:
            query |= models.Q(**{f"{field}__icontains": search})
        return qs.filter(query) if query else qs

    def apply_ordering(self, qs, ordering: str):
        ordering = (ordering or "").strip()
        if not ordering:
            default = self.meta.get("ordering") or []
            return qs.order_by(*default) if default else qs.order_by("pk")
        field = ordering.lstrip("-")
        if field in {item["name"] for item in self.meta["fields"]}:
            return qs.order_by(ordering)
        return qs.order_by("pk")

    def apply_company_scope(self, qs, *, company_id: str = ""):
        if not company_id:
            return qs
        field_names = {field.name for field in self.model._meta.get_fields()}
        if "company" in field_names:
            return qs.filter(company_id=company_id)
        if "tenant" in field_names:
            return qs.filter(tenant_id=company_id)
        if "owner" in field_names:
            return qs
        return qs

    def serialize(self, obj: models.Model) -> dict[str, Any]:
        data = model_to_dict(obj)
        data["id"] = str(obj.pk)
        for field in self.meta["fields"]:
            name = field["name"]
            if field["sensitive"]:
                data.pop(name, None)
                continue
            if name in data:
                data[name] = self.json_safe(data[name])
        return data

    @staticmethod
    def json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (Decimal, UUID)):
            return str(value)
        if isinstance(value, models.Model):
            return str(value.pk)
        if isinstance(value, File) or hasattr(value, "url"):
            try:
                return value.url
            except Exception:
                return getattr(value, "name", "") or ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): CRUDService.json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [CRUDService.json_safe(v) for v in value]
        if isinstance(value, ValidationError):
            return value.message_dict
        return str(value)
