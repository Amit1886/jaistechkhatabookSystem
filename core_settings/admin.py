from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.text import Truncator
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from datetime import datetime
from pathlib import Path
import re
import os
import sys
import tempfile
from urllib.parse import urlencode

from .models import (
    UISettings,
    CompanySettings,
    AppSettings,
    ModuleSettings,
    FeatureSettings,
    SaaSSettings,
    DesktopRelease,
    LandingVideo,
    LandingPageSettings,
    LandingClient,
    LandingUseCase,
    LandingReview,
    LandingMarketingFeature,
    LandingPricingRow,
    SettingCategory,
    SettingDefinition,
    SettingValue,
    SettingHistory,
    SettingPermission,
)

@admin.register(UISettings)
class UISettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("🎨 Colors", {
            "fields": ("primary_color","secondary_color","success_color","danger_color")
        }),
        ("🌙 Theme", {
            "fields": ("theme_mode",)
        }),
        ("📐 Layout", {
            "fields": ("sidebar_position","sidebar_collapsed")
        }),
        ("🧭 Navigation", {
            "fields": (
                "show_dashboard","show_party","show_transaction",
                "show_commerce","show_reports","show_settings"
            )
        }),
    )

    def has_add_permission(self, request):
        return not UISettings.objects.exists()


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ("company_name", "mobile", "email")


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("🏢 Company", {"fields": ("company_name", "currency_symbol", "financial_year_start")}),
        ("📊 Dashboard", {"fields": ("show_profit_loss", "show_daily_summary")}),
        ("👤 Users", {"fields": ("allow_user_signup", "allow_social_login")}),
        ("🔐 System", {"fields": ("maintenance_mode", "enable_chat", "enable_notifications")}),
    )

    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

@admin.register(ModuleSettings)
class ModuleSettingsAdmin(admin.ModelAdmin):
    list_display = ("module", "enabled")
    list_editable = ("enabled",)

@admin.register(FeatureSettings)
class FeatureSettingsAdmin(admin.ModelAdmin):
    list_display = ("feature", "enabled")
    list_editable = ("enabled",)

@admin.register(SaaSSettings)
class SaaSSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("🏢 Core", {"fields": ("enable_multi_company","enable_multi_user")}),
        ("💳 Subscription", {"fields": ("enable_subscription","enable_trial","trial_days")}),
        ("🔐 Advanced", {"fields": ("enable_audit_logs","enable_api_access")}),
    )

    def has_add_permission(self, request):
        return not SaaSSettings.objects.exists()


@admin.register(DesktopRelease)
class DesktopReleaseAdmin(admin.ModelAdmin):
    list_display = ("version", "is_published", "published_at", "updated_at")
    fields = (
        "version",
        "is_published",
        "published_at",
        "windows_exe",
        "sha256",
        "download_link",
        "android_apk",
        "android_sha256",
        "apk_download_link",
        "notes",
        "desktop_logs_link",
        "updated_at",
    )
    readonly_fields = ("sha256", "android_sha256", "download_link", "apk_download_link", "desktop_logs_link", "updated_at")

    def has_add_permission(self, request):
        # Singleton: only one row.
        return not DesktopRelease.objects.exists()

    def download_link(self, obj):
        if not obj or not obj.windows_exe:
            return "No EXE uploaded"
        url = reverse("desktop-release-download")
        return format_html('<a class="button" href="{}">Download EXE</a>', url)

    download_link.short_description = "Download"

    def apk_download_link(self, obj):
        if not obj or not getattr(obj, "android_apk", None):
            return "No APK uploaded"
        url = reverse("android-release-download")
        return format_html('<a class="button" href="{}">Download APK</a>', url)

    apk_download_link.short_description = "Android APK"

    def desktop_logs_link(self, obj):
        url = reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_desktop_logs")
        return format_html('<a class="button" href="{}">View Desktop Logs</a>', url)

    desktop_logs_link.short_description = "Desktop Logs"

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "desktop-logs/",
                self.admin_site.admin_view(self.desktop_logs_view),
                name=f"{opts.app_label}_{opts.model_name}_desktop_logs",
            ),
        ]
        return custom + urls

    def _desktop_log_file_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        env_path = (os.getenv("KP_DESKTOP_LOG_FILE") or "").strip()
        if env_path:
            try:
                candidates.append(Path(os.path.expandvars(env_path)).expanduser())
            except Exception:
                pass

        # Prefer Django's resolved handler filename if available (matches actual runtime).
        try:
            handler_path = ((getattr(settings, "LOGGING", {}) or {}).get("handlers", {}) or {}).get("desktop_file", {}).get("filename")
            if handler_path:
                candidates.append(Path(str(handler_path)))
        except Exception:
            pass

        # Prefer Django's resolved desktop data dir if available.
        try:
            desktop_dir = getattr(settings, "DESKTOP_DATA_DIR", None)
            if desktop_dir:
                base_dir = Path(str(desktop_dir))
                candidates.append(base_dir / "logs" / "desktop.log")
                candidates.append(base_dir / "logs" / "django.log")
        except Exception:
            pass

        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or ""
        if base:
            candidates.append(Path(base) / "JaisTechKhataBook" / "logs" / "desktop.log")
            candidates.append(Path(base) / "JaisTechKhataBook" / "logs" / "django.log")
        try:
            candidates.append(Path(tempfile.gettempdir()) / "JaisTechKhataBook" / "logs" / "desktop.log")
        except Exception:
            pass
        # Dev fallback: local logs folder (if any)
        candidates.append(Path.cwd() / "desktop.log")
        return candidates

    def _tail_text(self, path: Path, max_bytes: int = 200_000) -> str:
        try:
            if not path.exists() or not path.is_file():
                return ""
            size = path.stat().st_size
            start = max(0, size - max_bytes)
            with open(path, "rb") as f:
                if start:
                    f.seek(start)
                data = f.read()
            # Try UTF-8, fallback to CP1252 (common on Windows logs)
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = data.decode("cp1252", errors="replace")

            # Strip ANSI escape sequences (colors) so logs are readable in admin.
            try:
                text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
            except Exception:
                pass
            return text
        except Exception:
            return ""

    def _allowed_log_base_dirs(self) -> list[Path]:
        bases: list[Path] = []
        try:
            desktop_dir = getattr(settings, "DESKTOP_DATA_DIR", None)
            if desktop_dir:
                bases.append((Path(str(desktop_dir)) / "logs").resolve())
        except Exception:
            pass

        base = (os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or "").strip()
        if base:
            try:
                bases.append((Path(base) / "JaisTechKhataBook" / "logs").resolve())
            except Exception:
                pass
        try:
            bases.append((Path(tempfile.gettempdir()) / "JaisTechKhataBook" / "logs").resolve())
        except Exception:
            pass
        try:
            bases.append(Path.cwd().resolve())
        except Exception:
            pass

        # De-dup while preserving order
        seen: set[str] = set()
        dedup: list[Path] = []
        for p in bases:
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(p)
        return dedup

    def _is_safe_log_file(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            return False

        if resolved.suffix.lower() != ".log":
            return False

        for base in self._allowed_log_base_dirs():
            try:
                if resolved.is_relative_to(base):
                    return True
            except Exception:
                continue
        return False

    def desktop_logs_view(self, request):
        # Staff only (admin already enforces, but keep explicit)
        if not (request.user and request.user.is_active and request.user.is_staff):
            context = dict(self.admin_site.each_context(request), title="Desktop Logs", error="Admin access required")
            return TemplateResponse(request, "admin/core_settings/desktop_logs.html", context)

        candidates = self._desktop_log_file_candidates()
        # De-dup (preserve order)
        dedup: list[Path] = []
        seen = set()
        for p in candidates:
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(p)

        selected = (request.GET.get("file") or request.POST.get("file") or "").strip()
        selected_path = None
        for p in dedup:
            if selected and str(p).lower() == selected.lower():
                selected_path = p
                break
        if selected_path is None:
            # Prefer an existing file by default, otherwise fallback to first candidate.
            for p in dedup:
                try:
                    if p.exists() and p.is_file():
                        selected_path = p
                        break
                except Exception:
                    continue
        if selected_path is None and dedup:
            selected_path = dedup[0]

        # Clear/Delete actions (POST).
        if request.method == "POST" and selected_path:
            action = (request.POST.get("action") or "").strip().lower()
            if action in {"clear", "delete"}:
                if not self._is_safe_log_file(selected_path):
                    messages.error(
                        request,
                        "Refused: only *.log files inside the desktop logs folders can be cleared/deleted.",
                    )
                else:
                    if action == "clear":
                        try:
                            selected_path.parent.mkdir(parents=True, exist_ok=True)
                            selected_path.write_text("", encoding="utf-8")
                            messages.success(request, f"Cleared log: {selected_path}")
                        except Exception as e:
                            messages.error(request, f"Failed to clear log: {e}")
                    else:
                        try:
                            selected_path.unlink(missing_ok=True)
                            messages.success(request, f"Deleted log file: {selected_path}")
                        except Exception as e:
                            messages.error(request, f"Failed to delete log file: {e}")

                query = urlencode(
                    {
                        "file": str(selected_path),
                        "t": str(int(timezone.now().timestamp())),
                    }
                )
                return redirect(f"{request.path}?{query}")

        selected_exists = False
        selected_size_bytes = ""
        selected_mtime = ""
        if selected_path:
            try:
                selected_exists = bool(selected_path.exists() and selected_path.is_file())
                if selected_exists:
                    st = selected_path.stat()
                    selected_size_bytes = str(int(st.st_size))
                    selected_mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                selected_exists = False

        content = self._tail_text(selected_path) if selected_path else ""
        if content:
            # Keep the page snappy.
            content = Truncator(content).chars(120_000)

        candidate_items = []
        for p in dedup:
            try:
                exists = bool(p.exists())
            except Exception:
                exists = False
            candidate_items.append(
                {
                    "value": str(p),
                    "label": f"{p} (missing)" if not exists else str(p),
                    "exists": exists,
                }
            )

        context = dict(
            self.admin_site.each_context(request),
            title="Desktop Logs",
            now=timezone.now(),
            debug={
                "is_frozen": bool(getattr(sys, "frozen", False)),
                "desktop_mode": bool(getattr(settings, "DESKTOP_MODE", False)),
                "desktop_app_version": (os.getenv("DESKTOP_APP_VERSION_CODE") or os.getenv("DESKTOP_APP_VERSION") or "").strip(),
                "kp_desktop_log_file": (os.getenv("KP_DESKTOP_LOG_FILE") or "").strip(),
                "localappdata": (os.getenv("LOCALAPPDATA") or "").strip(),
                "appdata": (os.getenv("APPDATA") or "").strip(),
                "cwd": str(Path.cwd()),
                "desktop_data_dir": str(getattr(settings, "DESKTOP_DATA_DIR", "")),
            },
            candidates=candidate_items,
            selected=str(selected_path) if selected_path else "",
            selected_exists=selected_exists,
            selected_size_bytes=selected_size_bytes,
            selected_mtime=selected_mtime,
            content=content,
            hint="Logs are read from this machine's local disk (desktop app only).",
        )
        return TemplateResponse(request, "admin/core_settings/desktop_logs.html", context)


@admin.register(SettingCategory)
class SettingCategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "sort_order")
    list_editable = ("sort_order",)


@admin.register(SettingDefinition)
class SettingDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "category", "data_type", "scope")
    list_filter = ("category", "data_type", "scope")
    search_fields = ("label", "key")


@admin.register(SettingValue)
class SettingValueAdmin(admin.ModelAdmin):
    list_display = ("definition", "owner", "updated_at")
    list_filter = ("definition__category",)


@admin.register(SettingHistory)
class SettingHistoryAdmin(admin.ModelAdmin):
    list_display = ("definition", "owner", "created_at", "updated_by")
    list_filter = ("definition__category",)


@admin.register(SettingPermission)
class SettingPermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "category", "can_view", "can_edit", "hidden")
    list_filter = ("role", "category")


@admin.register(LandingVideo)
class LandingVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "video_url", "video_file")
    ordering = ("sort_order", "-created_at")
    fields = ("title", "is_active", "sort_order", "thumbnail", "video_file", "video_url", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LandingPageSettings)
class LandingPageSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Brand", {"fields": ("brand_name",)}),
        ("Hero", {"fields": ("hero_kicker", "hero_title", "hero_subtitle")}),
        ("Stats", {"fields": ("stat_businesses", "stat_invoices", "stat_reports")}),
        ("Clients", {"fields": ("show_clients", "clients_title")}),
        ("Use Cases", {"fields": ("show_usecases", "usecases_kicker", "usecases_title", "usecases_subtitle")}),
        ("Videos", {"fields": ("show_videos", "videos_kicker", "videos_title", "videos_subtitle")}),
        ("Reviews", {"fields": ("show_reviews", "reviews_title", "reviews_subtitle")}),
        ("CTA", {"fields": ("cta_title", "cta_subtitle")}),
        ("Support / Contact", {"fields": ("support_title", "support_subtitle", "support_phone", "support_email", "support_address", "map_embed_url")}),
        ("WhatsApp", {"fields": ("show_whatsapp_widget", "whatsapp_number", "whatsapp_default_message")}),
        ("Social", {"fields": ("show_social_bar", "facebook_url", "instagram_url", "youtube_url", "twitter_url", "linkedin_url")}),
        ("Chatbot", {"fields": ("show_chatbot_widget", "enable_websocket_chat")}),
        ("Download Popup", {"fields": ("show_download_popup",)}),
    )

    def has_add_permission(self, request):
        return not LandingPageSettings.objects.exists()


@admin.register(LandingClient)
class LandingClientAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "website_url")
    ordering = ("sort_order", "name")


@admin.register(LandingUseCase)
class LandingUseCaseAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("title",)
    ordering = ("sort_order", "title")


@admin.register(LandingReview)
class LandingReviewAdmin(admin.ModelAdmin):
    list_display = ("name", "rating", "source", "is_active", "sort_order", "created_at")
    list_filter = ("is_active", "source", "rating")
    search_fields = ("name", "review")
    ordering = ("sort_order", "-created_at")


@admin.register(LandingMarketingFeature)
class LandingMarketingFeatureAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("title", "description")
    ordering = ("sort_order", "title")


@admin.register(LandingPricingRow)
class LandingPricingRowAdmin(admin.ModelAdmin):
    list_display = ("label", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("label",)
    ordering = ("sort_order", "label")
    fields = (
        "label",
        "is_active",
        "sort_order",
        ("free_state", "free_text"),
        ("pro_state", "pro_text"),
        ("pro_max_state", "pro_max_text"),
    )
