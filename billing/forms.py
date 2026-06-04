# full path: ~/myproject/khatapro/billing/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Plan
from .models import Commerce

from billing.services import ensure_free_plan, get_effective_plan


User = get_user_model()

class SubscriptionForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.all(), widget=forms.RadioSelect)


class CommerceForm(forms.ModelForm):
    class Meta:
        model = Commerce
        fields = [
            "business_name",
            "category",
            "gst_number",
            "contact_number",
            "address",
        ]
        widgets = {
            "business_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Business Name"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category"}),
            "gst_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "GST Number"}),
            "contact_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact Number"}),
            "address": forms.Textarea(attrs={"class": "form-control", "placeholder": "Business Address", "rows": 3}),
        }


class LinkedBillingUserForm(forms.Form):
    """
    Create/update a user linked under one Billing Profile (owner) via accounts.User.parent.
    """

    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"class": "form-control"}))
    mobile = forms.CharField(required=False, max_length=15, widget=forms.TextInput(attrs={"class": "form-control"}))
    username = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))

    billing_role_type = forms.ChoiceField(
        required=True,
        choices=[
            ("sub_user", "Sub User"),
            ("supplier", "Supplier"),
            ("vendor", "Vendor"),
            ("customer", "Customer"),
            ("field_agent", "Field Agent"),
            ("ai_agent", "AI Agent"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Role Type",
    )
    billing_child_role = forms.CharField(
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Child Role (key)",
        help_text="Example: shop_manager / data_entry / field_executive",
    )
    is_active = forms.BooleanField(required=False, initial=True, label="Active")

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop("owner", None)
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        if self.instance is not None:
            self.fields["email"].initial = self.instance.email or ""
            self.fields["mobile"].initial = getattr(self.instance, "mobile", "") or ""
            self.fields["username"].initial = self.instance.username or ""
            self.fields["billing_role_type"].initial = getattr(self.instance, "billing_role_type", "") or "sub_user"
            self.fields["billing_child_role"].initial = getattr(self.instance, "billing_child_role", "") or ""
            self.fields["is_active"].initial = bool(getattr(self.instance, "is_active", True))

    def clean(self):
        cleaned = super().clean()
        owner = self.owner
        if not owner or not getattr(owner, "is_authenticated", False):
            raise forms.ValidationError("Owner is required.")

        role_type = (cleaned.get("billing_role_type") or "").strip()
        child_role = (cleaned.get("billing_child_role") or "").strip()

        # AI Agent assignable only by Admin/Superuser/staff.
        if role_type == "ai_agent":
            can_admin = bool(getattr(owner, "is_superuser", False) or getattr(owner, "is_staff", False))
            if not can_admin:
                # also allow billing_access_level admin
                can_admin = (getattr(owner, "billing_access_level", "") or "") == "admin"
            if not can_admin:
                raise forms.ValidationError("AI Agent role can be assigned by Admin only.")

        # Validate child-role key if provided
        if child_role:
            try:
                from billing.hierarchy import role_children

                allowed = {c["key"] for c in role_children(role_type)}
                if allowed and child_role not in allowed:
                    raise forms.ValidationError(f"Invalid child role for {role_type}.")
            except Exception:
                # if hierarchy module not available during migrations, skip strict validation
                pass

        email = (cleaned.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")

        qs = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError("This email is already registered.")

        mobile = (cleaned.get("mobile") or "").strip()
        if mobile:
            mqs = User.objects.filter(mobile=mobile)
            if self.instance is not None:
                mqs = mqs.exclude(id=self.instance.id)
            if mqs.exists():
                raise forms.ValidationError("This mobile is already registered.")

        # For create, password is required.
        if self.instance is None and not (cleaned.get("password") or "").strip():
            raise forms.ValidationError("Password is required for new users.")

        return cleaned

    @transaction.atomic
    def save(self):
        owner = self.owner
        cleaned = self.cleaned_data

        if self.instance is None:
            user = User(
                email=(cleaned.get("email") or "").strip().lower(),
                username=(cleaned.get("username") or "").strip() or None,
                mobile=(cleaned.get("mobile") or "").strip() or None,
                is_active=bool(cleaned.get("is_active", True)),
            )
            user.parent = owner
            user.billing_access_level = ""  # linked members are not dashboard owners by default
            user.billing_role_type = (cleaned.get("billing_role_type") or "").strip()
            user.billing_child_role = (cleaned.get("billing_child_role") or "").strip()
            user.set_password((cleaned.get("password") or "").strip())
            try:
                from billing.hierarchy import apply_billing_defaults_to_user

                apply_billing_defaults_to_user(user, overwrite=False)
            except Exception:
                pass
            user.save()
            try:
                ensure_free_plan(user)
            except Exception:
                pass
        else:
            user = self.instance
            user.email = (cleaned.get("email") or "").strip().lower()
            user.username = (cleaned.get("username") or "").strip() or None
            user.mobile = (cleaned.get("mobile") or "").strip() or None
            user.is_active = bool(cleaned.get("is_active", True))
            user.parent = owner
            user.billing_role_type = (cleaned.get("billing_role_type") or "").strip()
            user.billing_child_role = (cleaned.get("billing_child_role") or "").strip()
            pw = (cleaned.get("password") or "").strip()
            if pw:
                user.set_password(pw)
            try:
                from billing.hierarchy import apply_billing_defaults_to_user

                apply_billing_defaults_to_user(user, overwrite=False)
            except Exception:
                pass
            user.save()

        # Ensure profiles exist (used across the system)
        try:
            from khataapp.models import UserProfile as KhataProfile

            plan = get_effective_plan(owner) or get_effective_plan(user)
            profile, _ = KhataProfile.objects.get_or_create(user=user)
            if plan and getattr(profile, "plan_id", None) != getattr(plan, "id", None):
                profile.plan = plan
            if not profile.mobile and user.mobile:
                profile.mobile = user.mobile
            if not profile.full_name and user.username:
                profile.full_name = user.username
            profile.save()
        except Exception:
            pass

        try:
            from accounts.models import UserProfile as AccountsUserProfile
            from core_settings.models import CompanySettings

            owner_accounts_profile = AccountsUserProfile.objects.filter(user=owner).select_related("company").first()
            company = owner_accounts_profile.company if owner_accounts_profile and owner_accounts_profile.company_id else None
            if not company:
                company = CompanySettings.objects.first()
            AccountsUserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "company": company,
                    "full_name": (getattr(user, "first_name", "") or user.username or "Member"),
                    "mobile": user.mobile or "",
                    "business_name": getattr(owner_accounts_profile, "business_name", "") if owner_accounts_profile else "",
                    "plan": get_effective_plan(owner),
                },
            )
        except Exception:
            pass

        return user
