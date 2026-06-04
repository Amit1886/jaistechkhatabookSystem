from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.db import models
from pydantic import BaseModel, ConfigDict, Field, create_model

from core.metadata.scanner import model_metadata, model_key


class DynamicSchemaFactory:
    """Builds runtime Pydantic contracts from Django model metadata.

    The FastAPI CRUD transport still accepts a generic envelope for maximum
    compatibility, but these generated schemas are the source of truth consumed
    by Swagger, Flutter, admin builders, and external API clients.
    """

    def schema_payload(self, model: type[models.Model]) -> dict[str, Any]:
        meta = model_metadata(model)
        return {
            "model": meta["key"],
            "read": self.json_schema(self.read_schema(model)),
            "create": self.json_schema(self.create_schema(model)),
            "update": self.json_schema(self.update_schema(model)),
            "filters": self.filter_schema(meta),
            "ordering": [field["name"] for field in meta["fields"] if not field["sensitive"]],
        }

    def read_schema(self, model: type[models.Model]) -> type[BaseModel]:
        fields = {}
        for field in model._meta.get_fields():
            if self.skip_field(field):
                continue
            python_type = self.python_type(field)
            default = None if getattr(field, "null", False) or getattr(field, "blank", False) else ...
            fields[field.name] = (python_type | None, Field(default=default, title=str(field.verbose_name).title()))
        return self._create_model(model, "Read", fields)

    def create_schema(self, model: type[models.Model]) -> type[BaseModel]:
        fields = {}
        for field in model._meta.get_fields():
            if self.skip_field(field) or self.read_only(field):
                continue
            python_type = self.write_python_type(field)
            default = None if getattr(field, "null", False) or getattr(field, "blank", False) else ...
            fields[field.name] = (python_type | None, Field(default=default, title=str(field.verbose_name).title()))
        return self._create_model(model, "Create", fields)

    def update_schema(self, model: type[models.Model]) -> type[BaseModel]:
        fields = {}
        for field in model._meta.get_fields():
            if self.skip_field(field) or self.read_only(field):
                continue
            fields[field.name] = (
                self.write_python_type(field) | None,
                Field(default=None, title=str(field.verbose_name).title()),
            )
        return self._create_model(model, "Update", fields)

    @staticmethod
    def filter_schema(meta: dict[str, Any]) -> dict[str, Any]:
        return {
            field["name"]: {
                "type": field["type"],
                "label": field["label"],
                "choices": field["choices"],
                "relation": field["relation"],
            }
            for field in meta["fields"]
            if field["filterable"]
        }

    @staticmethod
    def json_schema(schema: type[BaseModel]) -> dict[str, Any]:
        if hasattr(schema, "model_json_schema"):
            return schema.model_json_schema()
        return schema.schema()

    @staticmethod
    def skip_field(field: models.Field) -> bool:
        return bool(getattr(field, "one_to_many", False) or getattr(field, "auto_created", False))

    @staticmethod
    def read_only(field: models.Field) -> bool:
        return bool(getattr(field, "primary_key", False) or getattr(field, "auto_created", False))

    def write_python_type(self, field: models.Field):
        if isinstance(field, (models.ForeignKey, models.OneToOneField)):
            return int | str
        if getattr(field, "many_to_many", False):
            return list[int | str]
        return self.python_type(field)

    @staticmethod
    def python_type(field: models.Field):
        if isinstance(field, (models.IntegerField, models.AutoField, models.BigAutoField, models.PositiveIntegerField)):
            return int
        if isinstance(field, (models.FloatField,)):
            return float
        if isinstance(field, models.DecimalField):
            return Decimal
        if isinstance(field, models.BooleanField):
            return bool
        if isinstance(field, models.DateTimeField):
            return datetime
        if isinstance(field, models.DateField):
            return date
        if isinstance(field, models.TimeField):
            return time
        if isinstance(field, models.JSONField):
            return dict[str, Any] | list[Any]
        if isinstance(field, models.FileField):
            return str
        return str

    @staticmethod
    def _create_model(model: type[models.Model], suffix: str, fields: dict[str, Any]) -> type[BaseModel]:
        name = f"{model._meta.app_label}_{model._meta.model_name}_{suffix}"
        try:
            return create_model(name, __config__=ConfigDict(from_attributes=True), **fields)
        except TypeError:
            return create_model(name, **fields)


schema_factory = DynamicSchemaFactory()
