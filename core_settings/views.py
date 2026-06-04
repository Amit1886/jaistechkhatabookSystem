from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json
from django.urls import reverse

from core_settings.permissions import has_feature
from core_settings.models import CompanySettings, UISettings, AppSettings
from core_settings.services import (
    get_settings_payload,
    apply_updates,
    undo_last_change,
    build_ai_hints,
    get_status_cards,
)
from khataapp.models import UserProfile
from billing.models import Plan, PlanPermissions
from billing.models import FeatureRegistry, UserFeatureOverride
from django.contrib.auth import get_user_model
from validation.models import FraudAlert


def party_disabled(request):
    return HttpResponse("❌ Party module disabled by admin")


@login_required
def settings_dashboard(request):
    """Main settings dashboard with plan-wise permissions"""

    # Get user's plan and permissions
    user_profile = UserProfile.objects.filter(user=request.user).first()
    user_plan = user_profile.plan if user_profile else None
    plan_permissions = user_plan.get_permissions() if user_plan else None

    # 🔐 Subscription permission
    if (not (request.user.is_staff or request.user.is_superuser)) and (not has_feature(request.user, "settings.advanced")):
        return HttpResponse("❌ Your plan does not allow Settings access")

    company = CompanySettings.objects.first()
    ui = UISettings.objects.first()
    app = AppSettings.objects.first()

    if request.method == "POST":

        # 🏢 Company
        if has_feature(request.user, "company"):
            company.company_name = request.POST.get("company_name")
            company.mobile = request.POST.get("mobile")
            company.email = request.POST.get("email")
            company.save()

        # 🎨 UI
        if has_feature(request.user, "ui"):
            ui.primary_color = request.POST.get("primary_color")
            ui.secondary_color = request.POST.get("secondary_color")
            ui.theme_mode = request.POST.get("theme_mode")
            ui.sidebar_position = request.POST.get("sidebar_position")
            ui.save()

        messages.success(request, "✅ Settings Updated Successfully")
        return redirect("settings")

    return render(request, "core_settings/dashboard.html", {
        "company": company,
        "ui": ui,
        "app": app,
        "user_plan": user_plan,
        "plan_permissions": plan_permissions,
    })


@login_required
def plan_permissions_view(request):
    """View all plans and their permissions - Admin Only"""
    
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponse("❌ Admin access required")

    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        plan = Plan.objects.filter(id=plan_id).first()
        if not plan:
            messages.error(request, "Plan not found.")
            return redirect("core_settings:plan_permissions")

        perms = plan.get_permissions()

        bool_fields = [
            "allow_dashboard",
            "allow_reports",
            "allow_pdf_export",
            "allow_excel_export",
            "allow_analytics",
            "allow_add_party",
            "allow_edit_party",
            "allow_delete_party",
            "allow_add_transaction",
            "allow_edit_transaction",
            "allow_delete_transaction",
            "allow_bulk_transaction",
            "allow_commerce",
            "allow_warehouse",
            "allow_orders",
            "allow_inventory",
            "allow_whatsapp",
            "allow_sms",
            "allow_email",
            "allow_ledger",
            "allow_credit_report",
            "allow_settings",
            "allow_users",
            "allow_api_access",
        ]

        for field in bool_fields:
            setattr(perms, field, request.POST.get(field) == "on")

        max_parties = request.POST.get("max_parties")
        if max_parties is not None and str(max_parties).isdigit():
            perms.max_parties = int(max_parties)

        perms.save()
        messages.success(request, f"Permissions updated for {plan.name}.")
        return redirect("core_settings:plan_permissions")
    
    plans = Plan.objects.filter(active=True).prefetch_related('permissions')
    
    return render(request, "core_settings/plan_permissions.html", {
        "plans": plans,
    })


@login_required
def user_feature_overrides_view(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponse("❌ Admin access required")

    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by("email")
    features = FeatureRegistry.objects.filter(active=True).order_by("group", "label")

    selected_user_id = request.GET.get("user_id") or (users.first().id if users.exists() else None)
    selected_user = User.objects.filter(id=selected_user_id).first() if selected_user_id else None

    if request.method == "POST":
        selected_user_id = request.POST.get("user_id")
        selected_user = User.objects.filter(id=selected_user_id).first()
        if not selected_user:
            messages.error(request, "User not found.")
            return redirect("core_settings:user_feature_overrides")

        # Clear existing overrides
        UserFeatureOverride.objects.filter(user=selected_user).delete()

        for feature in features:
            field_name = f"feature_{feature.id}"
            if field_name in request.POST:
                UserFeatureOverride.objects.create(
                    user=selected_user,
                    feature=feature,
                    is_enabled=True
                )

        messages.success(request, "User overrides updated.")
        return redirect(f"{reverse('core_settings:user_feature_overrides')}?user_id={selected_user.id}")

    overrides = {}
    if selected_user:
        for ov in UserFeatureOverride.objects.filter(user=selected_user):
            overrides[ov.feature_id] = ov.is_enabled

    return render(request, "core_settings/user_feature_overrides.html", {
        "users": users,
        "features": features,
        "selected_user": selected_user,
        "overrides": overrides,
    })


@login_required
def user_permissions_view(request):
    """View current user's plan permissions"""
    
    user_profile = UserProfile.objects.filter(user=request.user).first()
    user_plan = user_profile.plan if user_profile else None
    plan_permissions = user_plan.get_permissions() if user_plan else None
    
    if not user_plan:
        messages.error(request, "❌ No plan assigned to your account")
        return redirect("accounts:dashboard")
    
    # Get all permission fields
    permission_categories = {
        "📊 Dashboard & Reports": {
            "allow_dashboard": plan_permissions.allow_dashboard if plan_permissions else False,
            "allow_reports": plan_permissions.allow_reports if plan_permissions else False,
            "allow_pdf_export": plan_permissions.allow_pdf_export if plan_permissions else False,
            "allow_excel_export": plan_permissions.allow_excel_export if plan_permissions else False,
            "allow_analytics": plan_permissions.allow_analytics if plan_permissions else False,
        },
        "👥 Party Management": {
            "allow_add_party": plan_permissions.allow_add_party if plan_permissions else False,
            "allow_edit_party": plan_permissions.allow_edit_party if plan_permissions else False,
            "allow_delete_party": plan_permissions.allow_delete_party if plan_permissions else False,
            "max_parties": plan_permissions.max_parties if plan_permissions else 0,
        },
        "💰 Transactions": {
            "allow_add_transaction": plan_permissions.allow_add_transaction if plan_permissions else False,
            "allow_edit_transaction": plan_permissions.allow_edit_transaction if plan_permissions else False,
            "allow_delete_transaction": plan_permissions.allow_delete_transaction if plan_permissions else False,
            "allow_bulk_transaction": plan_permissions.allow_bulk_transaction if plan_permissions else False,
        },
        "📦 Commerce & Warehouse": {
            "allow_commerce": plan_permissions.allow_commerce if plan_permissions else False,
            "allow_warehouse": plan_permissions.allow_warehouse if plan_permissions else False,
            "allow_orders": plan_permissions.allow_orders if plan_permissions else False,
            "allow_inventory": plan_permissions.allow_inventory if plan_permissions else False,
        },
        "📱 Communication": {
            "allow_whatsapp": plan_permissions.allow_whatsapp if plan_permissions else False,
            "allow_sms": plan_permissions.allow_sms if plan_permissions else False,
            "allow_email": plan_permissions.allow_email if plan_permissions else False,
        },
        "📊 Ledger & Credit": {
            "allow_ledger": plan_permissions.allow_ledger if plan_permissions else False,
            "allow_credit_report": plan_permissions.allow_credit_report if plan_permissions else False,
        },
        "🔧 Admin & Settings": {
            "allow_settings": plan_permissions.allow_settings if plan_permissions else False,
            "allow_users": plan_permissions.allow_users if plan_permissions else False,
            "allow_api_access": plan_permissions.allow_api_access if plan_permissions else False,
        },
    }
    
    return render(request, "core_settings/user_permissions.html", {
        "user_plan": user_plan,
        "permission_categories": permission_categories,
    })


# ---------------- Unified Settings Center ----------------

@login_required
def settings_center(request):
    if (not (request.user.is_staff or request.user.is_superuser)) and (not has_feature(request.user, "settings.advanced")):
        return HttpResponse("Your plan does not allow Settings access")
    payload = get_settings_payload(request.user)
    ai_hints = build_ai_hints(payload)
    status_cards = get_status_cards(payload)
    if request.user.is_staff or request.user.is_superuser:
        open_alerts = FraudAlert.objects.filter(status=FraudAlert.Status.OPEN).count()
    else:
        open_alerts = FraudAlert.objects.filter(owner=request.user, status=FraudAlert.Status.OPEN).count()
    return render(request, "core_settings/settings_dashboard.html", {
        "settings_payload": payload,
        "ai_hints": ai_hints,
        "status_cards": status_cards,
        "open_alerts_count": open_alerts,
    })


@login_required
def api_settings_all(request):
    payload = get_settings_payload(request.user)
    response = {
        "status": "ok",
        "settings": payload,
        "ai_hints": build_ai_hints(payload),
        "status_cards": get_status_cards(payload),
    }
    return JsonResponse(response)


@login_required
@require_POST
def api_settings_update(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    action = payload.get("action", "update")
    if action == "undo":
        key = payload.get("key")
        if not key:
            return JsonResponse({"status": "error", "message": "Missing key"}, status=400)
        value = undo_last_change(request.user, key)
        if value is None:
            return JsonResponse({"status": "error", "message": "Nothing to undo"}, status=400)
        return JsonResponse({"status": "ok", "key": key, "value": value})

    updates = payload.get("updates", [])
    results = apply_updates(request.user, updates)
    return JsonResponse({"status": "ok", "results": results})
