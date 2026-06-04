from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.conf import settings
from django.utils.html import format_html

from vendors.models import Vendor, VendorMembership
from .models import (
    User, UserProfile, DailySummary, BusinessSnapshot,
    ExpenseCategory, Expense, LoyaltyProgram, MembershipTier,
    LoyaltyPoints, PointsTransaction, SpecialOffer, OTP 
)

try:
    from khataapp.models import UserProfile as KhataUserProfile
except Exception:  # pragma: no cover
    KhataUserProfile = None

try:
    from billing.models import FeatureRegistry, PlanFeature, Subscription as BillingSubscription, UserFeatureOverride
except Exception:  # pragma: no cover
    FeatureRegistry = None
    PlanFeature = None
    BillingSubscription = None
    UserFeatureOverride = None

try:
    from saas.models import UserPermissionGraph
except Exception:  # pragma: no cover
    UserPermissionGraph = None


class VendorMembershipInline(admin.TabularInline):
    model = VendorMembership
    extra = 0
    fields = ("vendor", "role", "is_active")
    readonly_fields = ("vendor",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class SubUserInline(admin.TabularInline):
    model = User
    fk_name = "parent"
    extra = 0
    fields = ("id", "username", "email", "mobile", "primary_role", "store_type", "is_active")
    readonly_fields = fields
    can_delete = False
    verbose_name = "Sub-user"
    verbose_name_plural = "Sub-users (owner → users)"

    def has_add_permission(self, request, obj=None):
        return False


if UserPermissionGraph is not None:
    class UserPermissionGraphInline(admin.TabularInline):
        model = UserPermissionGraph
        extra = 0
        fields = ("seller", "role", "inherit_from_owner", "is_active", "overrides_json", "updated_at")
        readonly_fields = ("updated_at",)
        can_delete = False
        verbose_name = "Permission graph"
        verbose_name_plural = "APGS Permission Graphs"

        def has_add_permission(self, request, obj=None):
            # Allow creating a graph row to assign role + overrides.
            return True


if KhataUserProfile is not None:
    class KhataUserProfileInline(admin.StackedInline):
        model = KhataUserProfile
        extra = 0
        can_delete = False
        fk_name = "user"
        verbose_name = "Business profile"
        verbose_name_plural = "Business Profile (Billing settings)"


if BillingSubscription is not None:
    class BillingSubscriptionInline(admin.TabularInline):
        model = BillingSubscription
        extra = 0
        fields = ("plan", "status", "start_date", "end_date", "trial_end", "auto_renew", "created_at")
        readonly_fields = ("created_at",)
        can_delete = False


if UserFeatureOverride is not None:
    class UserFeatureOverrideInline(admin.TabularInline):
        model = UserFeatureOverride
        extra = 0
        fields = ("feature", "is_enabled", "note", "updated_at")
        readonly_fields = ("updated_at",)
        autocomplete_fields = ("feature",) if hasattr(UserFeatureOverride, "_meta") else ()
        can_delete = True

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    change_list_template = "admin/accounts/user/change_list.html"
    change_form_template = "admin/accounts/user/change_form.html"
    list_display = ('username', 'email', 'mobile', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'mobile')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    save_on_top = True
    actions = [
        "grant_ecommerce_vendor_access",
        "revoke_ecommerce_vendor_access",
        "sync_feature_registry_action",
        "initialize_feature_overrides_action",
        "suspend_users_action",
        "enable_users_action",
        "reset_passwords_action",
    ]

    inlines = (
        [VendorMembershipInline, SubUserInline]
        + (([KhataUserProfileInline] if KhataUserProfile is not None else []))  # type: ignore[name-defined]
        + (([BillingSubscriptionInline] if BillingSubscription is not None else []))  # type: ignore[name-defined]
        + (([UserFeatureOverrideInline] if UserFeatureOverride is not None else []))  # type: ignore[name-defined]
        + (([UserPermissionGraphInline] if UserPermissionGraph is not None else []))  # type: ignore[name-defined]
    )

    readonly_fields = (
        "saas_quick_links",
        "saas_role_summary",
        "saas_plan_summary",
        "saas_metrics_summary",
        "saas_features_summary",
        "saas_permissions_summary",
    )

    def get_fieldsets(self, request, obj=None):
        base = list(super().get_fieldsets(request, obj))
        snapshot = (
            "Centralized User Dashboard",
            {
                "fields": (
                    "saas_quick_links",
                    "saas_role_summary",
                    "saas_plan_summary",
                    "saas_metrics_summary",
                )
            },
        )
        access = (
            "Permissions / Access Control",
            {
                "fields": (
                    "store_type",
                    "primary_role",
                    "seller",
                    "permissions_json",
                    "saas_features_summary",
                    "saas_permissions_summary",
                )
            },
        )
        return [snapshot] + base + [access]

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            if not hasattr(response, "context_data") or response.context_data is None:
                return response
            cl = response.context_data.get("cl")
            if not cl:
                return response
            qs = cl.queryset
            response.context_data["be_user_metrics"] = {
                "total": qs.count(),
                "active": qs.filter(is_active=True).count(),
                "inactive": qs.filter(is_active=False).count(),
                "staff": qs.filter(is_staff=True).count(),
                "owners": qs.filter(primary_role="owner").count(),
            }
        except Exception:
            # Never block admin rendering for dashboard metrics.
            response.context_data["be_user_metrics"] = None
        return response

    @admin.display(description="Quick links")
    def saas_quick_links(self, obj: User):
        try:
            user_id = getattr(obj, "id", None)
            return format_html(
                "<a class='button' href='/saas/rbac/' target='_blank'>RBAC/APGS Registry</a> "
                "<a class='button' href='/billing/commerce-dashboard/' target='_blank'>Billing Commerce Dashboard</a> "
                "<a class='button' href='/superadmin/billing/userfeatureoverride/?user__id__exact={}' target='_blank'>Features & Services</a> "
                "<a class='button' href='/superadmin/saas/userpermissionoverride/?user__id__exact={}' target='_blank'>APGS Overrides</a>",
                user_id,
                user_id,
            )
        except Exception:
            return "-"

    @admin.display(description="Usage / Metrics")
    def saas_metrics_summary(self, obj: User):
        parts = []
        try:
            from billing.models import Order as BillingOrder

            parts.append(f"billing_orders={BillingOrder.objects.filter(user=obj).count()}")
        except Exception:
            pass
        try:
            from storefront.models import StorefrontOrder

            parts.append(f"storefront_orders={StorefrontOrder.objects.filter(user=obj).count()}")
        except Exception:
            pass
        try:
            from vendors.models import VendorMembership

            parts.append(f"vendor_access={VendorMembership.objects.filter(user=obj, is_active=True).count()}")
        except Exception:
            pass
        if not parts:
            return "-"
        return ", ".join(parts)

    @admin.display(description="Role summary")
    def saas_role_summary(self, obj: User):
        try:
            from accounts.roles import get_user_role

            return f"ERP role={get_user_role(obj).name}; primary_role={obj.primary_role or '-'}; store_type={obj.store_type or '-'}"
        except Exception:
            return f"primary_role={obj.primary_role or '-'}; store_type={obj.store_type or '-'}"

    @admin.display(description="Plan summary")
    def saas_plan_summary(self, obj: User):
        try:
            from billing.services import get_effective_plan

            plan = get_effective_plan(obj)
            if not plan:
                return "No plan"
            return f"{plan.name} (free={getattr(plan, 'is_free', False)})"
        except Exception:
            return "Plan lookup unavailable"

    @admin.display(description="Enabled features (plan)")
    def saas_features_summary(self, obj: User):
        try:
            from billing.services import get_effective_plan

            plan = get_effective_plan(obj)
            if not plan:
                return "-"
            keys = []
            if PlanFeature is not None:
                keys = list(
                    PlanFeature.objects.filter(plan=plan, enabled=True)
                    .select_related("feature")
                    .values_list("feature__key", flat=True)
                )
            if not keys:
                return "-"
            return format_html("<div style='max-width:680px; white-space:normal;'><code>{}</code></div>", ", ".join(keys))
        except Exception:
            return "Feature lookup unavailable"

    @admin.action(description="Sync feature registry (auto-add new features to plans)")
    def sync_feature_registry_action(self, request, queryset):
        try:
            from billing.services import sync_feature_registry

            sync_feature_registry()
            self.message_user(request, "Feature registry synced.")
        except Exception as exc:
            self.message_user(request, f"Feature sync failed: {exc}", level="ERROR")

    @admin.action(description="Initialize per-user feature toggles (creates overrides for ALL features)")
    def initialize_feature_overrides_action(self, request, queryset):
        if FeatureRegistry is None or UserFeatureOverride is None:
            self.message_user(request, "Feature system not available.", level="ERROR")
            return
        try:
            from billing.services import get_effective_plan, sync_feature_registry

            sync_feature_registry()
        except Exception:
            pass

        created = 0
        for u in queryset:
            plan = None
            try:
                from billing.services import get_effective_plan

                plan = get_effective_plan(u)
            except Exception:
                plan = None

            enabled_by_plan = set()
            if plan and PlanFeature is not None:
                enabled_by_plan = set(
                    PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature_id", flat=True)
                )

            for feature in FeatureRegistry.objects.filter(active=True):
                default_enabled = True if not plan else (feature.id in enabled_by_plan)
                _, was_created = UserFeatureOverride.objects.get_or_create(
                    user=u,
                    feature=feature,
                    defaults={"is_enabled": default_enabled},
                )
                if was_created:
                    created += 1

        self.message_user(request, f"Initialized user feature toggles. Created overrides={created}.")

    @admin.action(description="Suspend users (disable login)")
    def suspend_users_action(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Suspended users: {updated}")

    @admin.action(description="Enable users (allow login)")
    def enable_users_action(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Enabled users: {updated}")

    @admin.action(description="Reset passwords (generate new)")
    def reset_passwords_action(self, request, queryset):
        updated = 0
        for u in queryset:
            pwd = User.objects.make_random_password()
            u.set_password(pwd)
            u.last_login = None
            u.save(update_fields=["password", "last_login"])
            updated += 1
            # Show generated password in admin message (demo/dev convenience).
            self.message_user(request, f"{u.email or u.username}: new password = {pwd}")
        if not updated:
            self.message_user(request, "No users updated.")

    @admin.display(description="JSON RBAC keys")
    def saas_permissions_summary(self, obj: User):
        try:
            blob = getattr(obj, "permissions_json", None) or {}
            if not isinstance(blob, dict) or not blob:
                return "-"
            keys = ", ".join(sorted(str(k) for k in blob.keys())[:120])
            return format_html("<div style='max-width:680px; white-space:normal;'><code>{}</code></div>", keys)
        except Exception:
            return "-"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        Centralized user control (backend-only):
        Inject SaaS/RBAC/plan/subuser data into the existing admin user change page
        WITHOUT changing any templates.
        """
        extra_context = extra_context or {}
        try:
            obj = self.get_object(request, object_id)
            if obj:
                # Ensure every feature appears in the user panel automatically (no-code admin experience).
                try:
                    from billing.services import ensure_user_feature_overrides

                    ensure_user_feature_overrides(obj, sync_plan=True)
                except Exception:
                    pass

                # Ensure every permission node appears as a toggle row automatically (APGS no-code).
                try:
                    from saas.utils.registry import ensure_user_permission_overrides

                    ensure_user_permission_overrides(obj)
                except Exception:
                    pass

                # Sub-users (owner -> children)
                extra_context["sub_users"] = User.objects.filter(parent=obj).order_by("-id")[:50]

                # Plan + features
                try:
                    from billing.services import get_effective_plan
                    from billing.models import PlanFeature

                    plan = get_effective_plan(obj)
                    extra_context["plan"] = plan
                    if plan:
                        extra_context["enabled_features"] = list(
                            PlanFeature.objects.filter(plan=plan, enabled=True)
                            .select_related("feature")
                            .values_list("feature__key", flat=True)
                        )
                    else:
                        extra_context["enabled_features"] = []
                except Exception:
                    extra_context.setdefault("plan", None)
                    extra_context.setdefault("enabled_features", [])

                # Vendor memberships
                try:
                    extra_context["vendor_memberships"] = (
                        VendorMembership.objects.filter(user=obj, is_active=True).select_related("vendor").order_by("vendor__subdomain")
                    )
                except Exception:
                    extra_context.setdefault("vendor_memberships", [])

                # APGS graphs (optional)
                try:
                    from saas.models import UserPermissionGraph

                    extra_context["permission_graphs"] = (
                        UserPermissionGraph.objects.filter(user=obj, is_active=True).select_related("seller", "role").order_by("-id")
                    )
                except Exception:
                    extra_context.setdefault("permission_graphs", [])
        except Exception:
            pass
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def _get_default_vendor(self):
        sub = getattr(settings, "ECOM_DEFAULT_VENDOR_SUBDOMAIN", None) or "demo"
        return Vendor.objects.filter(subdomain=sub, is_active=True).first(), sub

    @admin.action(description="Grant E-commerce access (default vendor)")
    def grant_ecommerce_vendor_access(self, request, queryset):
        vendor, sub = self._get_default_vendor()
        if not vendor:
            self.message_user(
                request,
                f"Default vendor '{sub}' not found. Create a Vendor with subdomain '{sub}' first.",
                level="ERROR",
            )
            return

        created = 0
        updated = 0
        skipped_owner = 0
        for u in queryset:
            if getattr(vendor, "owner_id", None) == getattr(u, "id", None):
                skipped_owner += 1
                continue
            obj, was_created = VendorMembership.objects.get_or_create(
                vendor=vendor,
                user=u,
                defaults={"role": VendorMembership.Role.OWNER, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                if not obj.is_active or obj.role != VendorMembership.Role.OWNER:
                    obj.is_active = True
                    obj.role = VendorMembership.Role.OWNER
                    obj.save(update_fields=["is_active", "role"])
                    updated += 1

        self.message_user(
            request,
            f"Vendor '{vendor.subdomain}': granted access. Created={created}, Updated={updated}, Already owner={skipped_owner}.",
        )

    @admin.action(description="Revoke E-commerce access (default vendor)")
    def revoke_ecommerce_vendor_access(self, request, queryset):
        vendor, sub = self._get_default_vendor()
        if not vendor:
            self.message_user(
                request,
                f"Default vendor '{sub}' not found. Nothing to revoke.",
                level="ERROR",
            )
            return

        updated = 0
        skipped_owner = 0
        for u in queryset:
            if getattr(vendor, "owner_id", None) == getattr(u, "id", None):
                skipped_owner += 1
                continue
            m = VendorMembership.objects.filter(vendor=vendor, user=u, is_active=True).first()
            if not m:
                continue
            m.is_active = False
            m.save(update_fields=["is_active"])
            updated += 1

        self.message_user(
            request,
            f"Vendor '{vendor.subdomain}': revoked access. Updated={updated}, Skipped owner={skipped_owner}.",
        )

# Register User with custom admin
admin.site.register(User, CustomUserAdmin)

# Otp View Admin
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "created_at")
    search_fields = ("user__username",)

# Other models
admin.site.register(UserProfile)
admin.site.register(DailySummary)
admin.site.register(BusinessSnapshot)
admin.site.register(ExpenseCategory)
admin.site.register(Expense)

# Loyalty Program Admin
@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'points_per_rupee', 'points_to_rupee_ratio', 'min_redeem_points')
    list_editable = ('is_active', 'points_per_rupee', 'points_to_rupee_ratio', 'min_redeem_points')

# Membership Tier Admin
@admin.register(MembershipTier)
class MembershipTierAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'min_points_required', 'min_transaction_amount', 'upgrade_price', 'is_active')
    list_editable = ('min_points_required', 'min_transaction_amount', 'upgrade_price', 'is_active')
    list_filter = ('is_active', 'name')

# Loyalty Points Admin
@admin.register(LoyaltyPoints)
class LoyaltyPointsAdmin(admin.ModelAdmin):
    list_display = ('user', 'program', 'available_points', 'total_points', 'current_tier', 'total_earned')
    search_fields = ('user__username', 'user__email')
    list_filter = ('program', 'current_tier')
    readonly_fields = ('total_points', 'available_points', 'used_points', 'total_earned')

# Points Transaction Admin
@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ('loyalty_account', 'transaction_type', 'points', 'amount', 'description', 'created_at')
    search_fields = ('loyalty_account__user__username', 'description')
    list_filter = ('transaction_type', 'created_at')
    readonly_fields = ('created_at',)

# Special Offer Admin
@admin.register(SpecialOffer)
class SpecialOfferAdmin(admin.ModelAdmin):
    list_display = ('name', 'offer_type', 'is_active', 'bonus_points', 'discount_percentage', 'valid_from', 'valid_until')
    list_editable = ('is_active', 'bonus_points', 'discount_percentage')
    list_filter = ('offer_type', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('name', 'description')
