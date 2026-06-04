from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def default_download_token_expiry():
    return timezone.now() + timedelta(hours=2)


class Industry(TimestampedModel):
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=80, blank=True, default="store")
    sort_order = models.PositiveIntegerField(default=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Industries"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class AppPlatform(TimestampedModel):
    class PlatformType(models.TextChoices):
        WEB = "web", "Web App"
        ANDROID_APK = "android_apk", "Android APK"
        DESKTOP_EXE = "desktop_exe", "Desktop EXE"
        EMBEDDED_POS = "embedded_pos", "Embedded POS"
        SELF_CHECKOUT = "self_checkout", "Self Checkout Kiosk"
        PWA = "pwa", "PWA"
        TABLET_POS = "tablet_pos", "Tablet POS"
        MOBILE_POS = "mobile_pos", "Mobile POS"
        WINDOWS = "windows", "Windows Installer"
        LINUX = "linux", "Linux Installer"
        MAC = "mac", "Mac Installer"

    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    platform_type = models.CharField(max_length=30, choices=PlatformType.choices, db_index=True)
    icon = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=100, db_index=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class FeatureRegistry(TimestampedModel):
    class RolloutStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        BETA = "beta", "Beta"
        ROLLOUT = "rollout", "Rollout"
        STABLE = "stable", "Stable"
        DISABLED = "disabled", "Disabled"

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=120, unique=True)
    icon = models.CharField(max_length=80, blank=True, default="sparkles")
    description = models.TextField(blank=True, default="")
    permissions = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=40, default="1.0.0", db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    supported_platforms = models.ManyToManyField(AppPlatform, blank=True, related_name="features")
    industries = models.ManyToManyField(Industry, blank=True, related_name="features")
    rollout_status = models.CharField(max_length=20, choices=RolloutStatus.choices, default=RolloutStatus.STABLE, db_index=True)
    config_schema = models.JSONField(default=dict, blank=True)
    remote_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ModuleRegistry(TimestampedModel):
    class ModuleType(models.TextChoices):
        PAGE = "page", "Page"
        MENU = "menu", "Menu"
        DASHBOARD_CARD = "dashboard_card", "Dashboard Card"
        REPORT = "report", "Report"
        POS_MODULE = "pos_module", "POS Module"
        KIOSK_MODULE = "kiosk_module", "Kiosk Module"
        PLUGIN = "plugin", "Plugin"

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=120, unique=True)
    module_type = models.CharField(max_length=30, choices=ModuleType.choices, default=ModuleType.PAGE, db_index=True)
    icon = models.CharField(max_length=80, blank=True, default="grid")
    route_path = models.CharField(max_length=240, blank=True, default="")
    api_endpoint = models.CharField(max_length=240, blank=True, default="")
    component_key = models.CharField(max_length=120, blank=True, default="")
    version = models.CharField(max_length=40, default="1.0.0", db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    lazy_load = models.BooleanField(default=True)
    supported_platforms = models.ManyToManyField(AppPlatform, blank=True, related_name="modules")
    features = models.ManyToManyField(FeatureRegistry, blank=True, related_name="modules")
    industries = models.ManyToManyField(Industry, blank=True, related_name="modules")
    permissions = models.JSONField(default=list, blank=True)
    ui_schema = models.JSONField(default=dict, blank=True)
    remote_payload = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=100, db_index=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class IndustryModuleMap(TimestampedModel):
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name="module_maps")
    module = models.ForeignKey(ModuleRegistry, on_delete=models.CASCADE, related_name="industry_maps")
    is_required = models.BooleanField(default=True, db_index=True)
    default_enabled = models.BooleanField(default=True, db_index=True)
    config_overrides = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("industry", "module")

    def __str__(self):
        return f"{self.industry} -> {self.module}"


class SoftwareBuild(TimestampedModel):
    class BuildType(models.TextChoices):
        APK = "apk", "Android APK"
        DESKTOP = "desktop", "Desktop"
        POS = "pos", "POS Installer"
        KIOSK = "kiosk", "Self Checkout"
        EMBEDDED = "embedded", "Embedded POS"
        WEB = "web", "Web URL"
        PWA = "pwa", "PWA"
        PLAY_STORE = "play_store", "Google Play"
        APP_STORE = "app_store", "App Store"
        INDIA_STORE = "india_store", "Indian App Store"
        WINDOWS = "windows", "Windows"
        LINUX = "linux", "Linux"
        MAC = "mac", "Mac"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=120, unique=True)
    build_type = models.CharField(max_length=30, choices=BuildType.choices, db_index=True)
    platform = models.ForeignKey(AppPlatform, on_delete=models.SET_NULL, null=True, blank=True, related_name="software_builds")
    industries = models.ManyToManyField(Industry, blank=True, related_name="software_builds")
    modules = models.ManyToManyField(ModuleRegistry, blank=True, related_name="software_builds")
    version = models.CharField(max_length=50, default="1.0.0", db_index=True)
    build_number = models.CharField(max_length=60, blank=True, default="")
    installer_file = models.FileField(upload_to="distribution/builds/", blank=True, null=True)
    external_url = models.URLField(blank=True, default="")
    play_store_url = models.URLField(blank=True, default="")
    app_store_url = models.URLField(blank=True, default="")
    pwa_url = models.URLField(blank=True, default="")
    web_launch_url = models.URLField(blank=True, default="")
    release_notes = models.TextField(blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    signature = models.CharField(max_length=160, blank=True, default="")
    is_published = models.BooleanField(default=False, db_index=True)
    allow_public_download = models.BooleanField(default=True, db_index=True)
    requires_login = models.BooleanField(default=False, db_index=True)
    min_license_tier = models.CharField(max_length=60, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=100, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "title"]
        indexes = [
            models.Index(fields=["build_type", "is_published"]),
            models.Index(fields=["slug", "version"]),
        ]

    def save(self, *args, **kwargs):
        if self.installer_file and not self.sha256:
            try:
                pos = self.installer_file.tell()
                self.installer_file.seek(0)
                h = hashlib.sha256()
                for chunk in self.installer_file.chunks():
                    h.update(chunk)
                self.sha256 = h.hexdigest()
                self.installer_file.seek(pos)
            except Exception:
                pass
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} {self.version}"


class DownloadPermission(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="download_permissions")
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, null=True, blank=True, related_name="download_permissions")
    build = models.ForeignKey(SoftwareBuild, on_delete=models.CASCADE, related_name="download_permissions")
    can_view = models.BooleanField(default=True)
    can_download = models.BooleanField(default=True)
    can_launch = models.BooleanField(default=True)
    can_install_beta = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "build"]), models.Index(fields=["industry", "build"])]

    def is_active(self):
        return not self.expires_at or self.expires_at >= timezone.now()


class AppVersion(TimestampedModel):
    platform = models.ForeignKey(AppPlatform, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=50, db_index=True)
    min_supported_version = models.CharField(max_length=50, blank=True, default="")
    force_update = models.BooleanField(default=False, db_index=True)
    update_message = models.CharField(max_length=240, blank=True, default="")
    release_notes = models.TextField(blank=True, default="")
    is_current = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("platform", "version")


class RemoteConfig(TimestampedModel):
    class Scope(models.TextChoices):
        GLOBAL = "global", "Global"
        INDUSTRY = "industry", "Industry"
        USER = "user", "User"
        DEVICE = "device", "Device"

    key = models.SlugField(max_length=120)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.GLOBAL, db_index=True)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, null=True, blank=True, related_name="remote_configs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="remote_configs")
    device_uid = models.CharField(max_length=140, blank=True, default="", db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("key", "scope", "industry", "user", "device_uid")

    def __str__(self):
        return f"{self.scope}:{self.key}:v{self.version}"


class DeviceRegistry(TimestampedModel):
    class DeviceType(models.TextChoices):
        WEB = "web", "Web"
        ANDROID = "android", "Android"
        DESKTOP = "desktop", "Desktop"
        POS = "pos", "POS"
        KIOSK = "kiosk", "Kiosk"
        EMBEDDED = "embedded", "Embedded"
        PWA = "pwa", "PWA"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="distribution_devices")
    industry = models.ForeignKey(Industry, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    device_uid = models.CharField(max_length=140, unique=True)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices, db_index=True)
    platform = models.ForeignKey(AppPlatform, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    app_version = models.CharField(max_length=50, blank=True, default="", db_index=True)
    last_config_version = models.PositiveIntegerField(default=0)
    authorized = models.BooleanField(default=True, db_index=True)
    license_key_hash = models.CharField(max_length=128, blank=True, default="")
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def touch(self, *, ip_address=None, app_version=None):
        self.last_seen_at = timezone.now()
        if ip_address:
            self.ip_address = ip_address
        if app_version:
            self.app_version = app_version
        self.save(update_fields=["last_seen_at", "ip_address", "app_version", "updated_at"])

    def __str__(self):
        return self.device_uid


class AppInstallation(TimestampedModel):
    device = models.ForeignKey(DeviceRegistry, on_delete=models.CASCADE, related_name="installations")
    build = models.ForeignKey(SoftwareBuild, on_delete=models.CASCADE, related_name="installations")
    installed_version = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=30, default="installed", db_index=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("device", "build")


class DownloadToken(TimestampedModel):
    build = models.ForeignKey(SoftwareBuild, on_delete=models.CASCADE, related_name="download_tokens")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="download_tokens")
    token = models.CharField(max_length=80, unique=True, default=secrets.token_urlsafe)
    expires_at = models.DateTimeField(default=default_download_token_expiry, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def is_valid(self):
        return not self.used_at and self.expires_at >= timezone.now()
