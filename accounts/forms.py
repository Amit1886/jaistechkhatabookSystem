# accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from khataapp.models import UserProfile

User = get_user_model()


# ----------------- SIGNUP FORM -----------------
class SignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    mobile = forms.CharField(max_length=15, required=True, label="Mobile Number")

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.mobile = (self.cleaned_data.get("mobile") or "").strip() or None
        if commit:
            user.save()
        return user

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_mobile(self):
        mobile = (self.cleaned_data.get("mobile") or "").strip()
        if mobile and User.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError("This mobile number is already registered.")
        return mobile


class AgentSignupForm(SignupForm):
    referrer_code = forms.CharField(
        max_length=24,
        required=False,
        label="Referral Code (Optional)",
        help_text="If you have an agent/distributor code, enter it here.",
    )

    def clean_referrer_code(self):
        code = (self.cleaned_data.get("referrer_code") or "").strip().upper()
        if not code:
            return ""
        if not User.objects.filter(referral_code__iexact=code).exists():
            raise forms.ValidationError("Invalid referral code.")
        return code


# ----------------- LOGIN FORM -----------------
class LoginForm(forms.Form):
    ROLE_CHOICES = (
        ("user", "User"),
        ("admin", "Admin"),
        ("customer", "Customer"),
        ("supplier", "Supplier"),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=False,
        initial="user",
        label="Login as",
    )
    identifier = forms.CharField(
        max_length=150,
        help_text="Email ya mobile",
        label="Email or Mobile"
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label="Password"
    )
    use_otp = forms.BooleanField(
        required=False,
        initial=True,
        label="Login via OTP"
    )

    def clean(self):
        cleaned = super().clean()
        identifier = cleaned.get("identifier")
        if not identifier:
            raise forms.ValidationError("Please enter Email or Mobile.")
        return cleaned


# ----------------- OTP FORM -----------------
class OTPForm(forms.Form):
    code = forms.CharField(max_length=6, label="OTP")


# ----------------- EXTRA INFO FORM -----------------
class ExtraInfoForm(forms.Form):
    name = forms.CharField(max_length=150, label="Full Name")
    mobile = forms.CharField(max_length=15, label="Mobile Number")


# ----------------- CSV UPLOAD (Bulk Import) -----------------
class CSVUploadForm(forms.Form):
    file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="Upload a CSV file.",
    )

# ----------------- USER PROFILE FORM -----------------
class UserProfileForm(forms.ModelForm):
    # Stored on accounts.User (not on khataapp.UserProfile)
    billing_access_level = forms.ChoiceField(
        required=False,
        choices=[("", "—"), ("admin", "Admin"), ("user", "User")],
        label="Billing Access Level",
    )
    billing_role_type = forms.ChoiceField(
        required=False,
        choices=[
            ("", "—"),
            ("sub_user", "Sub User"),
            ("supplier", "Supplier"),
            ("vendor", "Vendor"),
            ("customer", "Customer"),
            ("field_agent", "Field Agent"),
            ("ai_agent", "AI Agent"),
        ],
        label="Billing Role Type",
    )
    billing_child_role = forms.ChoiceField(
        required=False,
        choices=[("", "—")],
        label="Billing Child Role",
    )

    class Meta:
        model = UserProfile
        fields = [
            "full_name", "mobile", "address",
            "business_name", "business_type", "gst_number",
            "profile_picture", "plan", "bank_name", "account_number",
            "ifsc_code", "upi_id", "qr_code"
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        can_edit_billing = bool(kwargs.pop("can_edit_billing", False))
        super().__init__(*args, **kwargs)

        # ✅ Lazy import to avoid circular dependency
        from billing.models import Plan

        if not self.instance.plan:
            basic_plan = Plan.objects.filter(name__iexact="Basic").first()
            if basic_plan:
                self.fields["plan"].initial = basic_plan

        # Populate billing hierarchy fields from `user`
        if user is not None:
            self.fields["billing_access_level"].initial = getattr(user, "billing_access_level", "") or ""
            self.fields["billing_role_type"].initial = getattr(user, "billing_role_type", "") or ""
            self.fields["billing_child_role"].initial = getattr(user, "billing_child_role", "") or ""

        # Dynamic child role choices based on role_type
        try:
            from billing.hierarchy import role_children
        except Exception:
            role_children = None

        try:
            posted_role_type = (self.data.get(self.add_prefix("billing_role_type")) or "").strip()
        except Exception:
            posted_role_type = ""
        current_role_type = posted_role_type or (self.fields["billing_role_type"].initial or "")

        child_choices = [("", "—")]
        if role_children and current_role_type:
            for item in role_children(current_role_type):
                child_choices.append((item["key"], item["label"]))
        self.fields["billing_child_role"].choices = child_choices

        if not can_edit_billing:
            for k in ("billing_access_level", "billing_role_type", "billing_child_role"):
                self.fields[k].disabled = True
