from __future__ import annotations

import os

from django.conf import settings
from django.core import signing
from django.db import models
from django.utils import timezone


class EnterpriseSetting(models.Model):
    DATA_TYPES = (
        ("string", "String"),
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("json", "JSON"),
        ("secret", "Secret"),
    )
    SCOPE_CHOICES = (
        ("public", "Public"),
        ("private", "Private"),
        ("mobile", "Mobile"),
        ("company", "Company"),
    )

    key = models.SlugField(max_length=140, unique=True, db_index=True)
    label = models.CharField(max_length=180)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="private", db_index=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default="string")
    value = models.JSONField(default=dict, blank=True)
    encrypted_value = models.TextField(blank=True, default="")
    env_key = models.CharField(max_length=120, blank=True, default="")
    default_value = models.JSONField(default=dict, blank=True)
    help_text = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enterprise_setting_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scope", "key")

    def __str__(self):
        return self.key

    def set_secret(self, raw_value: str) -> None:
        self.encrypted_value = signing.dumps(raw_value or "", salt="enterprise-setting")

    def get_secret(self) -> str:
        if not self.encrypted_value:
            return ""
        try:
            return signing.loads(self.encrypted_value, salt="enterprise-setting")
        except signing.BadSignature:
            return ""

    def resolved_value(self):
        if self.env_key:
            env_value = os.getenv(self.env_key)
            if env_value not in ("", None):
                return self.cast_value(env_value)
        if self.data_type == "secret":
            return self.get_secret()
        if self.value not in ({}, [], "", None):
            return self.value
        return self.default_value

    def cast_value(self, raw_value):
        if self.data_type == "boolean":
            return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
        if self.data_type == "number":
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                return raw_value
        return raw_value


class OfflineSyncBatch(models.Model):
    device_id = models.CharField(max_length=160, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="offline_sync_batches")
    operation_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, default="received", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def finish(self, *, success_count: int, error_count: int):
        self.success_count = success_count
        self.error_count = error_count
        self.status = "completed_with_errors" if error_count else "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["success_count", "error_count", "status", "completed_at"])


class OfflineSyncOperation(models.Model):
    batch = models.ForeignKey(OfflineSyncBatch, on_delete=models.CASCADE, related_name="operations")
    client_id = models.CharField(max_length=180, db_index=True)
    model_key = models.CharField(max_length=180, db_index=True)
    operation = models.CharField(max_length=30, db_index=True)
    object_pk = models.CharField(max_length=180, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="pending", db_index=True)
    error = models.TextField(blank=True, default="")
    client_timestamp = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=["model_key", "operation", "status"])]


class OfflineSyncConflict(models.Model):
    operation = models.ForeignKey(OfflineSyncOperation, on_delete=models.CASCADE, related_name="conflicts")
    model_key = models.CharField(max_length=180, db_index=True)
    object_pk = models.CharField(max_length=180, db_index=True)
    server_snapshot = models.JSONField(default=dict, blank=True)
    client_payload = models.JSONField(default=dict, blank=True)
    policy = models.CharField(max_length=80, default="server_timestamp_wins")
    resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
