# khatapro/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.static import serve as media_serve
from django.core.cache import cache
from khataapp.views import submit_contact, admin_contact_leads_count
from accounts import views as accounts_views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from commerce.api_sync import InvoiceSyncAPI, ObjectSyncAPI
from core_settings.desktop_release_views import (
    latest_desktop_release_api,
    download_desktop_release,
    public_download_desktop_release,
    latest_android_release_api,
    download_android_release,
    public_download_android_release,
)
from whatsapp import views as whatsapp_views
from whatsapp.webhooks import whatsapp_gateway_inbound_webhook, whatsapp_meta_webhook
from voice import views as voice_views
from chatbot.views import chatbot_reply
from vendors.shopify_views import shopify_oauth_callback
from apps.platform.workforce.interfaces.public_views import public_workforce_apply
from distribution import views as distribution_views
from enterprise_control import views as enterprise_views

# Import billing and commerce views for specific routes
from billing import views as billing_views
from commerce import views as commerce_views
from pos.views import POSView
from core_settings.health import healthcheck
from core_settings.admin_realtime import admin_dashboard_realtime
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import reverse
from django.urls import path, include
from whatsapp import setup_views as whatsapp_setup_views
import json
import re

# Auto discount engine (billing protection + ajax pricing)

def landing(request):
    # Vendor store (subdomain-based): if middleware resolved a vendor, render storefront home.
    if getattr(request, "vendor", None):
        from storefront.views import vendor_storefront_home

        return vendor_storefront_home(request)

    # Landing page download button (public): show only if a published bundle exists.
    desktop_download_url = ""
    desktop_download_label = ""
    android_download_url = ""
    android_download_label = ""
    try:
        from core_settings.models import DesktopRelease

        rel = DesktopRelease.objects.filter(pk=1).first()
        if rel and rel.is_published:
            if rel.windows_exe:
                desktop_download_url = reverse("desktop-release-public-download")
                desktop_download_label = f"Download Desktop ({rel.version})"
            if getattr(rel, "android_apk", None):
                android_download_url = reverse("android-release-public-download")
                android_download_label = f"Download APK ({rel.version})"
    except Exception:
        desktop_download_url = ""
        desktop_download_label = ""
        android_download_url = ""
        android_download_label = ""

    pricing_cards = []
    pricing_matrix = []
    pricing_compare_rows = []
    pricing_popular_index = 1
    try:
        from billing.models import Plan, FeatureRegistry, PlanFeature
        from decimal import Decimal
        from collections import OrderedDict

        def _format_inr(amount: Decimal) -> str:
            try:
                if amount is None:
                    return "0"
                amount = Decimal(str(amount))
                if amount == amount.to_integral():
                    return f"{int(amount):,}"
                return f"{amount.normalize():,}"
            except Exception:
                return str(amount or "0")

        plans_all = list(Plan.objects.filter(active=True))
        # Safety seed: ensure marketing pricing always shows 3 tiers (Free/Basic/Premium)
        # even if this database was created without the seed migration.
        if len(plans_all) < 3:
            Plan.objects.update_or_create(
                name="Free Plan",
                defaults={
                    "active": True,
                    "price": Decimal("0.00"),
                    "price_monthly": Decimal("0.00"),
                    "price_yearly": Decimal("0.00"),
                    "trial_days": 7,
                    "description": "Designed for new users who want to try basic billing with simple limits.",
                },
            )
            Plan.objects.update_or_create(
                name="Basic Plan",
                defaults={
                    "active": True,
                    "price": Decimal("499.00"),
                    "price_monthly": Decimal("499.00"),
                    "price_yearly": Decimal("4999.00"),
                    "trial_days": 0,
                    "description": "For growing businesses that need unlimited entries and better controls.",
                },
            )
            Plan.objects.update_or_create(
                name="Premium Plan",
                defaults={
                    "active": True,
                    "price": Decimal("999.00"),
                    "price_monthly": Decimal("999.00"),
                    "price_yearly": Decimal("9999.00"),
                    "trial_days": 0,
                    "description": "For advanced workflows, multi-outlet needs, and enterprise-level reporting.",
                },
            )
            plans_all = list(Plan.objects.filter(active=True))
        free_plan = next((p for p in plans_all if getattr(p, "is_free", False)), None)
        paid_plans = [p for p in plans_all if not free_plan or p.id != free_plan.id]
        paid_plans.sort(key=lambda p: (p.price_yearly or p.price_monthly or p.price or Decimal("0"), p.id))
        plans = ([free_plan] if free_plan else []) + paid_plans
        # Homepage pricing is designed for 3 columns (Free, Pro, Pro Max). Keep it predictable.
        plans = [p for p in plans if p is not None][:3]

        if plans:
            features = list(FeatureRegistry.objects.filter(active=True))
            enabled_by_plan = {}
            for plan in plans:
                enabled_by_plan[plan.id] = set(
                    PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature_id", flat=True)
                )

            # Pick a "popular" plan (middle plan when 2/3 plans exist).
            popular_plan_id = plans[min(1, len(plans) - 1)].id
            pricing_popular_index = next(
                (i for i, p in enumerate(plans) if p.id == popular_plan_id),
                min(1, max(len(plans) - 1, 0)),
            )

            tier_labels = ["Free", "Pro", "Pro Max"]
            default_titles = ["Starter Plan", "Essential Plan", "Enterprise Plan"]
            default_descriptions = [
                "Designed for new users who need a straightforward way to start billing and explore the workflow.",
                "For growing shops, retailers, and professionals needing inventory, POS, and daily operations control.",
                "For multi-outlet and high-volume businesses needing automation, insights, and consolidated reporting.",
            ]

            for idx, plan in enumerate(plans):
                is_popular = plan.id == popular_plan_id
                tier = tier_labels[idx] if idx < len(tier_labels) else "Plan"

                # Price preference: yearly > monthly > base price.
                display_price = plan.price_yearly or plan.price_monthly or plan.price or Decimal("0")
                if plan.is_free or display_price == Decimal("0"):
                    suffix = ""
                elif (plan.price_yearly or Decimal("0")) > 0:
                    suffix = "+18% GST / Per Year / Per Outlet"
                elif (plan.price_monthly or Decimal("0")) > 0:
                    suffix = "+18% GST / Per Month"
                else:
                    suffix = ""

                plan_feature_objs = [f for f in features if f.id in enabled_by_plan.get(plan.id, set())]
                plan_feature_objs.sort(key=lambda f: (str(f.group or ""), int(getattr(f, "sort_order", 0)), str(f.label)))
                card_features = [
                    {"label": f.label, "description": (f.description or "").strip()}
                    for f in plan_feature_objs[:6]
                ]

                if plan.is_free:
                    buttons = [
                        {"label": "Claim Free Setup", "url": "/accounts/signup/", "variant": "muted"},
                        {"label": "Book Demo", "url": "#support", "variant": "outline"},
                        {"label": "Contact Us", "contact": True, "variant": "outline"},
                    ]
                    offer_text = ""
                else:
                    buttons = [
                        {"label": "Book Demo", "url": "#support", "variant": "outline"},
                        {"label": "Pay Now", "url": f"/billing/public-checkout/?plan_id={plan.id}", "variant": "primary"},
                        {"label": "Contact Us", "contact": True, "variant": "outline"},
                    ]
                    offer_text = "Special Offer Available"

                pricing_cards.append(
                    {
                        "id": plan.id,
                        "tier": tier,
                        "name": (plan.name or "").strip() or ("Plan " + str(idx + 1)),
                        "title": default_titles[idx] if idx < len(default_titles) else "Plan",
                        "description": (plan.description or "").strip()
                        or (default_descriptions[idx] if idx < len(default_descriptions) else ""),
                        "badge": "Most Popular" if is_popular else "",
                        "popular": is_popular,
                        "price": f"&#8377;{_format_inr(display_price)}",
                        "suffix": suffix,
                        "features": card_features,
                        "offer_text": offer_text,
                        "buttons": buttons,
                    }
                )

            grouped = OrderedDict()
            for feat in sorted(features, key=lambda f: (str(f.group or ""), int(getattr(f, "sort_order", 0)), str(f.label))):
                grouped.setdefault((feat.group or "General").strip() or "General", []).append(feat)

            pricing_matrix = []
            for group_title, group_features in grouped.items():
                items = []
                for feat in group_features:
                    items.append(
                        {
                            "label": feat.label,
                            "description": (feat.description or "").strip(),
                            "enabled": [feat.id in enabled_by_plan.get(p.id, set()) for p in plans],
                        }
                    )
                pricing_matrix.append({"title": group_title, "items": items})

            def _cell_text(text: str):
                return {"state": "text", "text": text}

            def _cell_state(state: str, text: str = ""):
                return {"state": state, "text": text}

            def _is_free(plan_obj) -> bool:
                return bool(getattr(plan_obj, "is_free", False))

            def _text(free_text: str, paid_text: str):
                return [_cell_text(free_text if _is_free(p) else paid_text) for p in plans]

            def _ok_for_paid(trial_for_free: bool = False, ok_for_free: bool = False):
                cells = []
                for p in plans:
                    if _is_free(p):
                        if trial_for_free:
                            cells.append(_cell_state("trial", "Trial Only"))
                        else:
                            cells.append(_cell_state("ok") if ok_for_free else _cell_state("no"))
                    else:
                        cells.append(_cell_state("ok"))
                return cells

            pricing_compare_rows = [
                {
                    "label": "Access Duration ⏳",
                    "cells": [
                        _cell_text(
                            f"{max(int(getattr(p, 'trial_days', 0) or 0), 7)} Days Trial" if _is_free(p) else "1 Year Subscription"
                        )
                        for p in plans
                    ],
                },
                {"label": "Supported Devices 💻📱", "cells": _text("Free - Only 1 Single Desktop or Mobile", "Unlimited Desktop + Mobile")},
                {"label": "Sales Entries 🧾", "cells": _text("10 / Per Day Only", "Unlimited")},
                {"label": "Expense Entries 💸", "cells": _text("5 / Per Day Only", "Unlimited")},
                {"label": "Customers 👥", "cells": _text("5 / Per Day Only", "Unlimited")},
                {"label": "Products 📦", "cells": _text("10 total product till free", "Unlimited")},
                {"label": "Categories 🗂️", "cells": _text("5 categories product till free", "Unlimited")},
                {"label": "Staff 👤", "cells": _text("1 staff till free", "Unlimited")},
                {"label": "Reports & Analytics 📊", "cells": _ok_for_paid(trial_for_free=False, ok_for_free=False)},
                {"label": "Quick Invoicing ⚡", "cells": _ok_for_paid(trial_for_free=True, ok_for_free=False)},
                {"label": "Invoice Printing (A4 / Thermal) 🖨️", "cells": _ok_for_paid(trial_for_free=False, ok_for_free=True)},
                {"label": "Custom Invoice Branding 🎨", "cells": _ok_for_paid(trial_for_free=False, ok_for_free=False)},
                {"label": "GST Billing & Reporting 🧾", "cells": _ok_for_paid(trial_for_free=False, ok_for_free=False)},
                {"label": "Restaurant POS (Order, Table, KOT) 🍽️", "cells": _ok_for_paid(trial_for_free=True, ok_for_free=False)},
            ]
    except Exception:
        pricing_cards = []
        pricing_matrix = []
        pricing_compare_rows = []
        pricing_popular_index = 1

    landing_videos = []
    try:
        from core_settings.models import (
            LandingVideo,
            LandingPageSettings,
            LandingClient,
            LandingUseCase,
            LandingReview,
            LandingMarketingFeature,
            LandingPricingRow,
        )

        landing_videos = list(LandingVideo.objects.filter(is_active=True).order_by("sort_order", "-created_at")[:20])
    except Exception:
        landing_videos = []
        LandingPageSettings = None
        LandingClient = None
        LandingUseCase = None
        LandingReview = None
        LandingMarketingFeature = None
        LandingPricingRow = None

    landing = None
    landing_clients = []
    landing_usecases = []
    landing_reviews = []
    landing_features = []
    landing_pricing_rows = []

    try:
        if LandingPageSettings:
            landing = LandingPageSettings.get_solo()
        if LandingClient:
            landing_clients = list(
                LandingClient.objects.filter(is_active=True).order_by("sort_order", "name")[:60]
            )
        if LandingUseCase:
            landing_usecases = list(
                LandingUseCase.objects.filter(is_active=True).order_by("sort_order", "title")[:30]
            )
        if LandingReview:
            landing_reviews = list(
                LandingReview.objects.filter(is_active=True).order_by("sort_order", "-created_at")[:30]
            )
        if LandingMarketingFeature:
            landing_features = list(
                LandingMarketingFeature.objects.filter(is_active=True).order_by("sort_order", "title")[:30]
            )
        if LandingPricingRow:
            landing_pricing_rows = list(
                LandingPricingRow.objects.filter(is_active=True).order_by("sort_order", "label")[:60]
            )
    except Exception:
        landing = None
        landing_clients = []
        landing_usecases = []
        landing_reviews = []
        landing_features = []
        landing_pricing_rows = []

    # If pricing rows are configured in Admin, prefer them over the built-in defaults.
    if landing_pricing_rows and pricing_cards:
        pricing_compare_rows = []
        for row in landing_pricing_rows:
            pricing_compare_rows.append(
                {
                    "label": row.label,
                    "cells": [
                        {"state": row.free_state, "text": (row.free_text or "").strip()},
                        {"state": row.pro_state, "text": (row.pro_text or "").strip()},
                        {"state": row.pro_max_state, "text": (row.pro_max_text or "").strip()},
                    ][: len(pricing_cards)],
                }
            )

    if getattr(settings, "IS_FROZEN", False):
        return render(
            request,
            "core/desktop_splash.html",
            {
                "desktop_app_version": getattr(settings, "DESKTOP_APP_VERSION", "0.0.0"),
                "desktop_auto_redirect": True,
            },
        )
    return render(
        request,
        "core/landing.html",
        {
            "desktop_app_version": getattr(settings, "DESKTOP_APP_VERSION", "0.0.0"),
            "desktop_mode": bool(getattr(settings, "DESKTOP_MODE", False)),
            "desktop_download_url": desktop_download_url,
            "desktop_download_label": desktop_download_label or "Download Desktop App",
            "android_download_url": android_download_url,
            "android_download_label": android_download_label or "Download Android APK",
            "pricing_cards": pricing_cards,
            "pricing_matrix": pricing_matrix,
            "pricing_compare_rows": pricing_compare_rows,
            "pricing_popular_index": pricing_popular_index,
            "landing_videos": landing_videos,
            "landing": landing,
            "landing_clients": landing_clients,
            "landing_usecases": landing_usecases,
            "landing_reviews": landing_reviews,
            "landing_features": landing_features,
        },
    )


@csrf_exempt
@require_POST
def landing_send_app_link(request):
    """
    Public endpoint used by the landing-page download popup.

    Tries to send an SMS with app download links if SMS is configured.
    Always returns the computed links so the frontend can display fallback UI.
    """
    try:
        payload = {}
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            payload = json.loads((request.body or b"{}").decode("utf-8", errors="ignore") or "{}")
        else:
            payload = request.POST

        mobile_raw = (payload.get("mobile") or "").strip()
        mobile = re.sub(r"[^\d+]", "", mobile_raw)
        # Normalize India numbers (basic)
        if mobile.startswith("+"):
            digits = re.sub(r"\D", "", mobile)
        else:
            digits = re.sub(r"\D", "", mobile)
        if len(digits) < 10 or len(digits) > 15:
            return JsonResponse({"ok": False, "message": "Please enter a valid mobile number."}, status=400)

        ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
        throttle_key = f"landing_app_link:{ip}:{digits}"
        if cache.get(throttle_key):
            return JsonResponse({"ok": True, "status": "throttled", "message": "Please wait a moment and try again."})
        cache.set(throttle_key, True, 60)

        desktop_url = ""
        android_url = ""
        try:
            from core_settings.models import DesktopRelease

            rel = DesktopRelease.objects.filter(pk=1).first()
            if rel and rel.is_published:
                if rel.windows_exe:
                    desktop_url = request.build_absolute_uri(reverse("desktop-release-public-download"))
                if getattr(rel, "android_apk", None):
                    android_url = request.build_absolute_uri(reverse("android-release-public-download"))
        except Exception:
            desktop_url = ""
            android_url = ""

        if not desktop_url and not android_url:
            # Avoid sending a misleading SMS when no public release is available.
            return JsonResponse(
                {
                    "ok": True,
                    "status": "no_release",
                    "message": "Downloads are not published yet. Please use the Contact/Support section.",
                    "android_url": "",
                    "desktop_url": "",
                }
            )

        message_lines = ["Billentra app download links:"]
        if android_url:
            message_lines.append(f"Android: {android_url}")
        if desktop_url:
            message_lines.append(f"Windows: {desktop_url}")
        message_lines.append("Thank you!")
        sms_text = "\n".join(message_lines)

        # Try SMS send if available/configured.
        sms_result = {"ok": False, "status": "not_configured"}
        try:
            from sms_center.sms_service import send_sms

            sms_result = send_sms(mobile=digits, text_message=sms_text, purpose="download_links")
        except Exception:
            sms_result = {"ok": False, "status": "exception"}

        if sms_result.get("ok"):
            return JsonResponse(
                {
                    "ok": True,
                    "status": "sent",
                    "message": "Link sent successfully!",
                    "android_url": android_url,
                    "desktop_url": desktop_url,
                }
            )

        # Fallback: not configured (still return links)
        return JsonResponse(
            {
                "ok": True,
                "status": sms_result.get("status") or "not_configured",
                "message": "SMS is not configured right now. Please use the download buttons below.",
                "android_url": android_url,
                "desktop_url": desktop_url,
            }
        )
    except Exception:
        return JsonResponse({"ok": False, "message": "Something went wrong."}, status=500)

def privacy(request):
    return render(request, "core/privacy.html")

def terms(request):
    return render(request, "core/terms.html")

def apps_public(request):
    # Public "Apps" page: curated Shopify app recommendations (external links).
    desktop_download_url = ""
    desktop_download_label = ""
    android_download_url = ""
    android_download_label = ""
    try:
        from core_settings.models import DesktopRelease

        rel = DesktopRelease.objects.filter(pk=1).first()
        if rel and rel.is_published:
            if rel.windows_exe:
                desktop_download_url = reverse("desktop-release-public-download")
                desktop_download_label = f"Download Desktop ({rel.version})"
            if getattr(rel, "android_apk", None):
                android_download_url = reverse("android-release-public-download")
                android_download_label = f"Download APK ({rel.version})"
    except Exception:
        desktop_download_url = ""
        desktop_download_label = ""
        android_download_url = ""
        android_download_label = ""

    from vendors.services.shopify_recommendations import get_shopify_app_recommendations

    catalog = get_shopify_app_recommendations()
    apps = catalog.get("apps") or []
    categories = catalog.get("categories") or []

    return render(
        request,
        "core/apps_public.html",
        {
            "desktop_download_url": desktop_download_url,
            "desktop_download_label": desktop_download_label,
            "android_download_url": android_download_url,
            "android_download_label": android_download_label,
            "apps": apps,
            "categories": categories,
        },
    )

urlpatterns = [
    path("health/", healthcheck, name="healthcheck"),
    # JaisTech ERP production APIs. These are backend-driven and used by Flutter, POS, kiosk, and admin shells.
    path("api/", include("jaistech_erp.urls")),
    # Enterprise Control Center APIs (backend-driven web, Flutter, POS, kiosk)
    path("api/enterprise/", include("enterprise_control.urls")),
    path("api/auth/", enterprise_views.settings_api, name="enterprise-auth-context"),
    path("api/dashboard/", enterprise_views.dashboard_api, name="enterprise-dashboard-root"),
    path("api/permissions/", enterprise_views.permissions_api, name="enterprise-permissions-root"),
    path("api/modules/", enterprise_views.modules_api, name="enterprise-modules-root"),
    path("api/workspaces/", enterprise_views.workspaces_api, name="enterprise-workspaces-root"),
    path("api/theme/", enterprise_views.theme_api, name="enterprise-theme-root"),
    path("api/settings/", enterprise_views.settings_api, name="enterprise-settings-root"),
    path("api/system/app-config/", enterprise_views.system_app_config_api, name="system-app-config"),
    path("api/menu/", enterprise_views.menu_api, name="enterprise-menu-root"),
    path("api/widgets/", enterprise_views.widgets_api, name="enterprise-widgets-root"),
    path("api/reports/", enterprise_views.reports_api, name="enterprise-reports-root"),
    path("api/analytics/", enterprise_views.analytics_api, name="enterprise-analytics-root"),
    path("api/notifications/", enterprise_views.notifications_api, name="enterprise-notifications-root"),
    # ---------------- Specific API routes (MUST be before generic api/ includes) ----------------
    path("api/orders/live-feed/", commerce_views.api_orders_live_feed, name="api_orders_live_feed"),
    path("api/whatsapp/order-inbox/", commerce_views.api_whatsapp_order_inbox, name="api_whatsapp_order_inbox"),
    path("api/whatsapp/accounting/webhook/", whatsapp_views.whatsapp_accounting_webhook, name="whatsapp_accounting_webhook"),
    path("api/whatsapp/webhook/", whatsapp_views.whatsapp_unified_webhook, name="whatsapp_unified_webhook"),
    path("api/whatsapp/meta/<uuid:account_id>/webhook/", whatsapp_meta_webhook, name="whatsapp_meta_webhook"),
    path("api/whatsapp/gateway/<uuid:account_id>/inbound/", whatsapp_gateway_inbound_webhook, name="whatsapp_gateway_inbound_webhook"),
    path("api/voice/command/", voice_views.api_voice_command, name="api_voice_command"),
    # ---------------- Mobile APP ----------------
    path("api/", include("mobileapi.urls")),
    # Public Storefront APIs (required: /api/products/, /api/orders/, /api/cart/, ...)
    path("api/", include("storefront.api_urls")),
    path("api/", include("system_mode.urls")),
    path("api/", include("procurement.api_urls")),
    path("api/", include("smart_khata.api_urls")),
    path("api/", include("smart_bi.api_urls")),
    path("api/", include("khataapp.core_engine.api_urls")),

    # ---------------- API Docs & Auth ----------------
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="jwt-token"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),

    # ---------------- Universal SaaS APIs ----------------
    path("api/v1/users/", include("users.urls")),
    path("api/gateway/", include("api.gateway.urls")),
    path("api/v1/platform/identity/", include("apps.platform.identity.interfaces.api.urls")),
    path("api/v1/platform/core/", include("apps.platform.core.interfaces.api.urls")),
    path("api/v1/platform/saas/", include("apps.platform.saas_ecosystem.interfaces.api.urls")),
    path("api/v1/platform/tax/", include("apps.platform.tax_compliance.interfaces.api.urls")),
    path("api/v1/platform/reports/", include("apps.platform.reporting.interfaces.api.urls")),
    path("api/v1/platform/workforce/", include("apps.platform.workforce.interfaces.api.urls")),
    path("api/v1/location/", include("location.urls")),
    path("api/v1/hierarchy/", include("hierarchy.urls")),
    path("api/v1/leads/", include("leads.urls")),
    path("api/v1/marketing/", include("marketing.urls")),
    path("api/v1/notifications/", include("notifications.urls")),
    path("api/v1/fraud/", include("fraud_detection.urls")),
    path("api/v1/integrations/", include("api_integrations.urls")),
    path("api/v1/wallet/", include("wallet.urls")),
    path("api/v1/crm/", include("crm.urls")),
    path("api/v1/subscription/", include("subscription.urls")),
    path("api/v1/performance/", include("performance.urls")),
    path("api/v1/super-app/", include("superapp.urls")),
    path("api/v1/distribution/", include("distribution.urls")),
    path("api/v1/pos/", include("pos.urls")),
    path("api/v1/printers/", include("printer_config.urls")),
    path("api/v1/scanners/", include("scanner_config.urls")),
    path("api/v1/warehouses/", include("warehouse.urls")),
    path("api/v1/products/", include("products.urls")),
    path("api/v1/whatsapp/", include("whatsapp.api_urls")),
    path("api/v1/orders/", include("orders.urls")),
    path("api/v1/commission/", include("commission.urls")),
    path("api/v1/delivery/", include("delivery.urls")),
    path("api/v1/payments/", include("payments.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/v1/ai/", include("ai_engine.urls")),
    path("api/v1/realtime/", include("realtime.urls")),
    path("api/v1/retail-os/", include("retail_os.urls")),
    path("addons/demo_center/", include(("addons.demo_center.urls", "demo_center"), namespace="demo_center")),
    path("demo/", include(("addons.demo_center.urls", "demo_center"), namespace="demo_center_public")),
    # ---------------- Hybrid Sync (Desktop -> Cloud) ----------------
    path("api/v1/sync/invoices/", InvoiceSyncAPI.as_view(), name="invoice-sync"),
    path("api/v1/sync/push/", ObjectSyncAPI.as_view(), name="sync-push"),
    # ---------------- Desktop Releases (Cloud -> Desktop) ----------------
    path("api/v1/desktop/releases/latest/", latest_desktop_release_api, name="desktop-release-latest"),
    path("api/v1/desktop/releases/download/", download_desktop_release, name="desktop-release-download"),
    path("download/desktop/", public_download_desktop_release, name="desktop-release-public-download"),
    # ---------------- Android APK Releases (Cloud -> Mobile) ----------------
    path("api/v1/android/releases/latest/", latest_android_release_api, name="android-release-latest"),
    path("api/v1/android/releases/download/", download_android_release, name="android-release-download"),
    path("download/apk/", public_download_android_release, name="android-release-public-download"),

    # ---------------- POS UI ----------------
    path("pos/ui/", POSView.as_view(), name="pos-ui"),
    path("pos/self-checkout/", include(("selfcheckout.urls", "selfcheckout"), namespace="selfcheckout")),
    # ---------------- Sales (aliases for required flow URLs) ----------------
    path("sales/order/create/", commerce_views.add_order, name="sales_order_create_root"),
    # ---------------- Admin Addons (must come before admin.site.urls) ----------------
    path("superadmin/chatbot/", include("chatbot.urls")),
    # Public chatbot endpoint used by landing page widget
    path("chatbot/", include("chatbot.urls")),
    # ---------------- Admin ----------------
    path("superadmin/api/contact-leads-count/", admin_contact_leads_count, name="admin_contact_leads_count"),
    path("superadmin/api/dashboard-realtime/", admin_dashboard_realtime, name="admin_dashboard_realtime"),
    path('superadmin/', admin.site.urls),  # ✅ New admin URL

    # ---------------- KhataApp (homepage, parties, transactions, reports) ----------------
    path("app/khata/", include(("smart_khata.urls", "smart_khata"), namespace="smart_khata")),
    path("app/engine/", include(("khataapp.core_engine.urls", "central_engine"), namespace="central_engine")),
    path("app/", include("khataapp.urls")),
    path("landing/send-app-link/", landing_send_app_link, name="landing-send-app-link"),
    path("workforce/apply/", public_workforce_apply, name="public-workforce-apply"),
    path("integrations/shopify/oauth/callback/", shopify_oauth_callback, name="shopify-oauth-callback"),
    path("distributor/create/", accounts_views.agent_signup_view, name="distributor-create"),
    path("apps/", apps_public, name="apps-public"),
    path("downloads/", distribution_views.download_center, name="download-center"),
    path("downloads/file/<slug:slug>/", distribution_views.public_build_download, name="distribution-public-build-download"),
    path("", landing, name="landing"),   # 👈 HOME PAGE
    path("privacy-policy/", privacy),
    path("terms/", terms),
    
    # ---------------- Reports ----------------
    path('reports/', include(('reports.urls', 'reports'), namespace='reports')),
    # Backward-compatible short alias (requested): /report/transactions, etc.
    path("report/", include(("reports.urls", "reports"), namespace="report")),

    # ---------------- Smart BI ----------------
    path("smart-bi/", include(("smart_bi.urls", "smart_bi"), namespace="smart_bi")),

    # ---------------- Ledger / Receipts ----------------
    path("ledger/", include(("ledger.urls", "ledger"), namespace="ledger")),


    # ---------------- Accounts (login, signup, dashboard, OTP, etc.) ----------------
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # ---------------- Billing / Subscription Plans ----------------
    path("billing/", include(("billing.urls", "billing"), namespace="billing")),

    # ---------------- Commerce (orders, products, inventory, etc.) ----------------
    path('commerce/', include('commerce.urls', namespace='commerce')),

    # ---------------- SaaS (backend-only) ----------------
    path("saas/", include(("saas.urls", "saas"), namespace="saas")),

    # ---------------- Procurement (Supplier price comparison) ----------------
    path("procurement/", include(("procurement.urls", "procurement"), namespace="procurement")),

    # ---------------- Customer/Supplier Self-Service Portal ----------------
    path("portal/", include(("portal.urls", "portal"), namespace="portal")),

    # ---------------- Social Login (Google, Facebook via social_django) ----------------
    path('accounts/', include('allauth.urls')),

    # ---------------- Logout (default Django auth view) ----------------
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # ---------------- Direct choose-plan routes (optional, can override) ----------------
    path("billing/choose-plan/", billing_views.choose_plan, name="billing_choose_plan"),
    path("favicon.ico", RedirectView.as_view(url="/static/img/billentra-favicon.ico")),
    path("chatbot/flows/", RedirectView.as_view(url="/superadmin/chatbot/flows/", permanent=True)),
    path(
        "chatbot/flows/<int:flow_id>/builder/",
        RedirectView.as_view(pattern_name="chatbot_flow_builder", permanent=True),
    ),
    path(
        "chatbot/flows/create/",
        RedirectView.as_view(pattern_name="chatbot_flow_create", permanent=True),
    ),
    path(
        "chatbot/flows/<int:flow_id>/save/",
        RedirectView.as_view(pattern_name="chatbot_flow_save", permanent=True),
    ),
    path("superadmin/chatbot/", include("chatbot.urls")),
    # Public landing-page chatbot endpoint (used by homepage widget)
    path("chatbot/reply/", chatbot_reply, name="chatbot_reply_public"),
    path("chatbot/", RedirectView.as_view(url="/superadmin/chatbot/", permanent=True)),

    # ---------------- Contact Form Home Page Landing Page  ----------------
    path("contact/submit/", submit_contact, name="contact_submit"),

    # ---------------- Core Settings (Dashboard, Permissions, Plan Management) ----------------
    path("settings/sms/", include(("sms_center.urls", "sms_center"), namespace="sms_center")),
    path("settings/", include(("core_settings.urls", "core_settings"), namespace="core_settings")),

    # ---------------- AI Tools & Automation ----------------
    path("ai-tools/insights/", include(("ai_insights.urls", "ai_insights"), namespace="ai_insights")),
    path("ai-tools/ocr/", include(("ai_ocr.urls", "ai_ocr"), namespace="ai_ocr")),
    path("ai-tools/voice/", include(("voice.urls", "voice"), namespace="voice")),
    path("ai-tools/whatsapp/", include(("whatsapp.urls", "whatsapp"), namespace="whatsapp")),
    path("ai-tools/alerts/", include(("validation.urls", "validation"), namespace="validation")),
    path("automation/bank-import/", include(("bank_import.urls", "bank_import"), namespace="bank_import")),
    path("studio/", include(("content_studio.urls", "content_studio"), namespace="content_studio")),
    path("api/v1/studio/", include("content_studio.api_urls")),

    # Short alias requested: WhatsApp Setup Wizard in Django dashboard
    path("whatsapp/setup/", whatsapp_setup_views.whatsapp_setup_wizard, name="whatsapp_setup_wizard_alias"),
    path("whatsapp/", include("whatsapp_gateway.urls")),
]

# Optional (non-subdomain) storefront browsing, helpful for local/dev:
urlpatterns += [
    path("store/", include("storefront.urls")),
    # Auto Discount Engine (adds: /auto-discount/billing/ and /ajax/calculate-discount/)
    path("", include(("auto_discount.urls", "auto_discount"), namespace="auto_discount")),
]

# ---------------- Media and static files serving (local/dev + Desktop Mode) ----------------
# NOTE:
# - `django.conf.urls.static.static()` only returns patterns when `DEBUG=True`.
# - For Desktop Mode / offline-first builds (DEBUG=False), we still want media previews
#   to work (product images/videos, invoice PDFs, etc.) on localhost.
if settings.DEBUG or getattr(settings, "SERVE_STATICFILES", False):
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", media_serve, {"document_root": str(settings.MEDIA_ROOT)}),
    ]

# For packaged Desktop Mode: serve `/static/` from finders.
if getattr(settings, "SERVE_STATICFILES", False):
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", staticfiles_serve, {"insecure": True}),
    ]

