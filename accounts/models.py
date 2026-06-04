# accounts/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db.models import Sum
from django.utils.text import slugify
from decimal import Decimal
import secrets
from django.apps import apps
 


class LedgerEntry(models.Model):
    # ---- SOURCE TYPES (for tracking) ----
    ENTRY_SOURCE = (
        ('manual', 'Manual Entry'),
        ('order', 'Order Billing'),
        ('payment', 'Payment Received'),
        ('invoice', 'Subscription Invoice'),
    )

    # ---- TRANSACTION TYPES ----
    TXN_TYPES = (
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    )

    # ---- LINK TO CREDIT ACCOUNT (owner=user stored on CreditAccount) ----
    # NOTE: temporary allow null so migration can run if rows already exist.
    account = models.ForeignKey(
        "khataapp.CreditAccount",
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        null=True,      # first add as nullable, later make non-nullable after populating
        blank=True
    )

    # ---- PARTY LINK ----
    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="ledger_entries"
    )

    # ---- AMOUNT ----
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    txn_type = models.CharField(max_length=10, choices=TXN_TYPES)

    # ---- OPTIONAL BILLING FIELDS ----
    invoice_no = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=250, blank=True, null=True)

    # ---- BUSY/TALLY FIELDS ----
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ---- NOTES ----
    notes = models.TextField(blank=True, null=True)

    # ---- SOURCE TRACKING ----
    source = models.CharField(max_length=20, choices=ENTRY_SOURCE, default='manual')
    source_id = models.PositiveIntegerField(null=True, blank=True)

    # ---- DATES ----
    date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields_set = set(update_fields)
            # Prevent infinite recursion/perf issues when only updating computed balance.
            if update_fields_set and update_fields_set.issubset({"balance"}):
                return super().save(*args, **kwargs)

        # auto fill credit/debit from txn_type
        if self.txn_type == "credit":
            self.credit = self.amount
            self.debit = 0
        else:
            self.debit = self.amount
            self.credit = 0

        super().save(*args, **kwargs)
        # update running balance for this (account, party) pair
        self.update_running_balance()

    def update_running_balance(self):
        # Use account to calculate running balance (account may be null temporarily)
        if not self.account:
            return

        entries = LedgerEntry.objects.filter(
            account=self.account,
            party=self.party
        ).order_by("date", "id").only("id", "credit", "debit", "balance")

        running = Decimal("0.00")
        for e in entries:
            running += (e.credit - e.debit)
            if e.balance != running:
                # Avoid calling model.save() inside the loop (prevents recursion and speeds up).
                LedgerEntry.objects.filter(id=e.id).update(balance=running)

    def __str__(self):
        return f"{self.party.name} – {self.txn_type.upper()} ₹{self.amount}"

@property
def total_parties(self):
    from khataapp.models import Party
    return Party.objects.filter(owner=self.user).count()

@property
def total_transactions(self):
    from khataapp.models import Transaction
    return Transaction.objects.filter(party__owner=self.user).count()



# ----------------- OTP GENERATOR -----------------
def _gen_otp():
    """Generate a 6-digit random OTP"""
    return str(random.randint(100000, 999999))


# ----------------- CUSTOM USER MODEL -----------------
class SaaSRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", "SuperAdmin"
    STATE_ADMIN = "state_admin", "StateAdmin"
    DISTRICT_ADMIN = "district_admin", "DistrictAdmin"
    AREA_ADMIN = "area_admin", "AreaAdmin"
    SUPER_AGENT = "super_agent", "SuperAgent"
    AGENT = "agent", "Agent"
    CUSTOMER = "customer", "Customer"


class BillingAccessLevel(models.TextChoices):
    ADMIN = "admin", "Admin"
    USER = "user", "User"


class BillingRoleType(models.TextChoices):
    SUB_USER = "sub_user", "Sub User"
    SUPPLIER = "supplier", "Supplier"
    VENDOR = "vendor", "Vendor"
    CUSTOMER = "customer", "Customer"
    FIELD_AGENT = "field_agent", "Field Agent"
    AI_AGENT = "ai_agent", "AI Agent"


class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True)
    mobile = models.CharField(max_length=15, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=40, choices=SaaSRole.choices, blank=True, default="", db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Downline/upline hierarchy. Optional for backward compatibility.",
        db_index=True,
    )
    referral_code = models.CharField(max_length=24, unique=True, blank=True, null=True, default=None, db_index=True)
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_users",
        help_text="Referral attribution. May be same as parent in simple setups.",
    )

    email_verified = models.BooleanField(default=False)
    mobile_verified = models.BooleanField(default=False)
    is_social_login = models.BooleanField(default=False)
    is_otp_verified = models.BooleanField(default=False)

    # ---------------- SaaS extensions (Phase A safe) ----------------
    class StoreType(models.TextChoices):
        B2B = "b2b", "B2B"
        B2C = "b2c", "B2C"
        HYBRID = "hybrid", "Hybrid"

    store_type = models.CharField(max_length=12, choices=StoreType.choices, default=StoreType.HYBRID, db_index=True)
    primary_role = models.CharField(
        max_length=30,
        blank=True,
        default="",
        db_index=True,
        help_text="owner/manager/billing/warehouse/accounts/vendor/staff/custom",
    )
    permissions_json = models.JSONField(default=dict, blank=True)
    seller = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seller_users",
        help_text="Phase A: link user to Vendor. Phase B: replace with tenant FK.",
    )

    # ---------------- Billing Model Hierarchy (RBAC) ----------------
    billing_access_level = models.CharField(
        max_length=10,
        choices=BillingAccessLevel.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Admin/User access layer for billing model hierarchy.",
    )
    billing_role_type = models.CharField(
        max_length=20,
        choices=BillingRoleType.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Role type within billing hierarchy (sub_user/supplier/vendor/customer/field_agent/ai_agent).",
    )
    billing_child_role = models.CharField(
        max_length=30,
        blank=True,
        default="",
        db_index=True,
        help_text="Optional child role within selected billing_role_type (stored as key).",
    )


    groups = models.ManyToManyField(
        Group,
        related_name="custom_user_set",
        blank=True,
        help_text="Groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="custom_user_permissions_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    USERNAME_FIELD = "email"  # login by email
    REQUIRED_FIELDS = ["username", "mobile"]

    def save(self, *args, **kwargs):
        was_creating = self._state.adding
        if not self.referral_code:
            # Short, URL-safe code (no PII). Retry on the extremely rare collision.
            for _ in range(8):
                candidate = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()
                if not User.objects.filter(referral_code=candidate).exists():
                    self.referral_code = candidate
                    break
        super().save(*args, **kwargs)

        # Replace signals with creation lifecycle hook.
        if was_creating:
            try:
                LoyaltyProgram = apps.get_model("accounts", "LoyaltyProgram")
                LoyaltyPoints = apps.get_model("accounts", "LoyaltyPoints")
                MembershipTier = apps.get_model("accounts", "MembershipTier")
                program = LoyaltyProgram.objects.filter(is_active=True).first()
                if program:
                    default_tier = MembershipTier.objects.filter(is_active=True).order_by("min_points_required").first()
                    LoyaltyPoints.objects.get_or_create(
                        user=self,
                        program=program,
                        defaults={"current_tier": default_tier},
                    )
            except Exception:
                pass

    def has_permission(self, key: str) -> bool:
        """
        JSON-based RBAC (Phase A).
        """
        if not self.is_active:
            return False
        if self.is_superuser or self.is_staff:
            return True
        if (self.primary_role or "").strip().lower() == "owner":
            return True

        k = (key or "").strip()
        if not k:
            return False

        # Allow dotted permission keys in code (`order.create`) while storing canonical keys
        # as slugs (`order_create`). Feature keys (`feature.<key>`) are handled separately.
        canonical = k
        if not (k.startswith("feature.") or k.startswith("feature:")) and "." in k:
            canonical = k.replace(".", "_")

        # Subscription feature gate (Phase A):
        # Use explicit feature-keys to avoid accidentally gating normal RBAC permissions.
        #
        # Convention:
        # - `feature.<key>` or `feature:<key>` -> checks billing.FeatureRegistry key `<key>`
        if k.startswith("feature.") or k.startswith("feature:"):
            feature_key = k.split(".", 1)[1] if k.startswith("feature.") else k.split(":", 1)[1]
            feature_key = (feature_key or "").strip()
            if not feature_key:
                return False
            try:
                from billing.services import user_has_feature

                if not user_has_feature(self, feature_key):
                    return False
            except Exception:
                # If billing module isn't ready during migrations, don't hard-fail.
                pass

        try:
            blob = self.permissions_json or {}
            if isinstance(blob, dict):
                v = blob.get(canonical) if canonical != k else blob.get(k)
                if v in {True, 1, "1", "true", "yes", "on"}:
                    return True
                if v in {False, 0, "0", "false", "no", "off"}:
                    return False
        except Exception:
            pass

        role = (self.primary_role or "").strip().lower()
        role_defaults = {
            "billing": {"create_order", "create_invoice"},
            "warehouse": {"stock_inward", "stock_outward", "stock_adjust"},
            "accounts": {"ledger_view", "ledger_post", "payment_record"},
            "manager": {"approve_request", "view_reports"},
            "vendor": {"vendor_access", "store_settings"},
            "staff": set(),
        }
        if role in role_defaults and (canonical in role_defaults[role] or k in role_defaults[role]):
            return True

        # APGS (Advanced Permission Graph System) check (Phase A safe).
        try:
            from saas.utils.apgs import apgs_has_permission

            if apgs_has_permission(self, canonical):
                return True
        except Exception:
            pass

        try:
            return bool(super().has_perm(canonical) or self.groups.filter(name=canonical).exists())
        except Exception:
            return False

    def __str__(self):
        return self.username or self.email or str(self.mobile)


# ----------------- OTP MODEL -----------------
class OTP(models.Model):
    PURPOSES = (
        ("signup", "Signup"),
        ("login", "Login"),
        ("password_reset", "Password Reset"),
        ("verify_email", "Verify Email"),
        ("verify_mobile", "Verify Mobile"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otps"
    )
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    sent_to_email = models.EmailField(blank=True, null=True)
    sent_to_mobile = models.CharField(max_length=15, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified = models.BooleanField(default=False)
    resend_count = models.PositiveIntegerField(default=0)

    @classmethod
    def create_for(cls, user, purpose="signup", email=None, mobile=None, minutes=10):
        """Safely create OTP"""
        if not user.pk:
            raise ValueError("User must be saved before creating OTP")
        return cls.objects.create(
            user=user,
            code=_gen_otp(),
            purpose=purpose,
            sent_to_email=email,
            sent_to_mobile=mobile,
            expires_at=timezone.now() + timedelta(minutes=minutes),
        )

    def is_valid(self, code):
        return not self.verified and self.code == code and timezone.now() <= self.expires_at

    def mark_verified(self):
        self.verified = True
        self.save(update_fields=["verified"])

    def __str__(self):
        return f"OTP {self.code} for {self.user} ({self.purpose})"


# ----------------- USER PROFILE MODEL -----------------
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_profiles'
    )
    country = models.ForeignKey(
        "location.Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_user_profiles",
    )
    state = models.ForeignKey(
        "location.State",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_user_profiles",
    )
    district = models.ForeignKey(
        "location.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_user_profiles",
    )
    pincode = models.ForeignKey(
        "location.Pincode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_user_profiles",
    )

    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15)

    business_name = models.CharField(max_length=150, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    plan = models.ForeignKey(
        "billing.Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_userprofiles'
    )

    def __str__(self):
        return self.user.username


# ----------------- AUTO CREATE PROFILE ON USER CREATION -----------------
# @receiver(post_save, sender=User)  # signals removed (Phase A)
def create_staff_profile(sender, instance, created, **kwargs):
    # Disabled – handled by khataapp
    return None

class DailySummary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    total_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_transactions = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class BusinessSnapshot(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_snapshots"
    )
    date = models.DateField(db_index=True)

    # SALES
    sales_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sales_orders = models.PositiveIntegerField(default=0)

    # PURCHASE
    purchase_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    purchase_orders = models.PositiveIntegerField(default=0)

    # PAYMENTS
    payment_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_given = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # PARTY BALANCES
    receivable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_position = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    profit_loss = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
)

    # COUNTS
    total_parties = models.PositiveIntegerField(default=0)
    total_transactions = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} | Snapshot | {self.date}"

# ----------------- Expences Model -----------------
class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Expense(models.Model):
    class PaymentMode(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        BANK = "bank", "Bank Transfer"
        CREDIT = "credit", "Credit"
        OTHER = "other", "Other"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    expense_number = models.CharField(max_length=20, unique=True)
    expense_date = models.DateField()

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    description = models.TextField(blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    vendor_name = models.CharField(max_length=160, blank=True, default="")
    invoice_number = models.CharField(max_length=80, blank=True, default="")
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices, default=PaymentMode.CASH)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    receipt_file = models.FileField(upload_to="expense_receipts/", blank=True, null=True)
    ocr_status = models.CharField(max_length=30, blank=True, default="")
    ocr_text = models.TextField(blank=True, default="")
    ocr_payload = models.JSONField(default=dict, blank=True)
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.SUBMITTED)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expense_number} - ₹{self.amount_paid}"


# ----------------- LOYALTY AND MEMBERSHIP MODELS -----------------

class LoyaltyProgram(models.Model):
    """Main loyalty program configuration"""
    name = models.CharField(max_length=100, default="Default Loyalty Program")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Points earning rules
    points_per_rupee = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)  # 1 point per rupee
    min_transaction_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Points expiry
    points_expiry_days = models.PositiveIntegerField(default=365)  # 1 year

    # Redeem rules
    points_to_rupee_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0.01)  # 100 points = 1 rupee
    min_redeem_points = models.PositiveIntegerField(default=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class MembershipTier(models.Model):
    """Membership tiers with benefits"""
    TIER_CHOICES = (
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    )

    name = models.CharField(max_length=50, choices=TIER_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Requirements
    min_points_required = models.PositiveIntegerField(default=0)
    min_transaction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Benefits
    points_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)  # Extra points earned
    birthday_bonus_points = models.PositiveIntegerField(default=0)
    festival_bonus_points = models.PositiveIntegerField(default=0)

    # Pricing for upgrade
    upgrade_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['min_points_required']

    def __str__(self):
        return f"{self.display_name} (₹{self.upgrade_price})"


class LoyaltyPoints(models.Model):
    """User's loyalty points"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_points')
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE)

    # Points balance
    total_points = models.PositiveIntegerField(default=0)
    available_points = models.PositiveIntegerField(default=0)  # After expiry/used
    used_points = models.PositiveIntegerField(default=0)

    # Current tier
    current_tier = models.ForeignKey(MembershipTier, on_delete=models.SET_NULL, null=True, blank=True)

    # Transaction tracking
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Total amount spent
    last_transaction_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'program']

    def __str__(self):
        return f"{self.user.username} - {self.available_points} points"

    def add_points(self, points, transaction_amount=None, description=""):
        """Add points to user's account"""
        self.total_points += points
        self.available_points += points
        if transaction_amount:
            self.total_earned += transaction_amount
        self.last_transaction_date = timezone.now()
        self.save()

        # Create transaction record
        PointsTransaction.objects.create(
            loyalty_account=self,
            transaction_type='earn',
            points=points,
            amount=transaction_amount or 0,
            description=description
        )

        # Check for tier upgrade
        self.check_tier_upgrade()

    def redeem_points(self, points, description=""):
        """Redeem points"""
        if self.available_points < points:
            raise ValueError("Insufficient points")

        self.available_points -= points
        self.used_points += points
        self.save()

        # Create transaction record
        PointsTransaction.objects.create(
            loyalty_account=self,
            transaction_type='redeem',
            points=points,
            description=description
        )

    def check_tier_upgrade(self):
        """Check if user qualifies for higher tier"""
        eligible_tiers = MembershipTier.objects.filter(
            min_points_required__lte=self.total_points,
            min_transaction_amount__lte=self.total_earned,
            is_active=True
        ).order_by('-min_points_required')

        if eligible_tiers.exists():
            new_tier = eligible_tiers.first()
            if not self.current_tier or new_tier.min_points_required > self.current_tier.min_points_required:
                self.current_tier = new_tier
                self.save()


class PointsTransaction(models.Model):
    """Transaction history for points"""
    TRANSACTION_TYPES = (
        ('earn', 'Earned'),
        ('redeem', 'Redeemed'),
        ('bonus', 'Bonus'),
        ('expired', 'Expired'),
        ('adjustment', 'Adjustment'),
    )

    loyalty_account = models.ForeignKey(LoyaltyPoints, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    points = models.IntegerField()  # Positive for earn, negative for redeem
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Transaction amount that earned points
    description = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.loyalty_account.user.username} - {self.transaction_type} {self.points} points"


class SpecialOffer(models.Model):
    """Automatic special offers (birthday, festival)"""
    OFFER_TYPES = (
        ('birthday', 'Birthday'),
        ('festival', 'Festival'),
        ('anniversary', 'Anniversary'),
        ('custom', 'Custom'),
    )

    name = models.CharField(max_length=100)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES)
    description = models.TextField()

    # Conditions
    is_active = models.BooleanField(default=True)
    auto_apply = models.BooleanField(default=True)  # Auto-apply when conditions met

    # Points/Discount
    bonus_points = models.PositiveIntegerField(default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Validity
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    # Target users (optional filters)
    min_tier = models.ForeignKey(MembershipTier, on_delete=models.SET_NULL, null=True, blank=True)
    min_points = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.offer_type})"

    def is_valid_for_user(self, user):
        """Check if offer is valid for a user"""
        if not self.is_active:
            return False

        # Date validity
        today = timezone.now().date()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False

        # Get user's loyalty account
        try:
            loyalty = LoyaltyPoints.objects.get(user=user)
        except LoyaltyPoints.DoesNotExist:
            return False

        # Tier check
        if self.min_tier and (not loyalty.current_tier or loyalty.current_tier.min_points_required < self.min_tier.min_points_required):
            return False

        # Points check
        if loyalty.available_points < self.min_points:
            return False

        return True


# ----------------- AUTO CREATE LOYALTY ACCOUNT -----------------
# @receiver(post_save, sender=settings.AUTH_USER_MODEL)  # signals removed (Phase A)
def create_loyalty_account(sender, instance, created, **kwargs):
    return None
