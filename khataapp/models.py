# ~/myproject/khatapro/khataapp/models.py

from django.db import models
from django.conf import settings
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import secrets
from solo.models import SingletonModel
from django.contrib.auth import get_user_model
from khataapp.utils.whatsapp_utils import send_whatsapp_message
from django.urls import reverse

User = get_user_model()



# ---------------- PARTY MODEL ----------------
class Party(models.Model):
    PARTY_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='my_parties',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    gst = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pincode_text = models.CharField(max_length=12, blank=True, default="")
    pincode = models.ForeignKey(
        "location.Pincode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parties",
    )
    party_type = models.CharField(max_length=10, choices=PARTY_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional Business Details
    upi_id = models.CharField(max_length=50, blank=True, null=True)
    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_premium = models.BooleanField(default=False)

    # Extra Communication Details
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)
    sms_number = models.CharField(max_length=15, blank=True, null=True)

    # Credit Rating
    credit_grade = models.CharField(max_length=5, default='-', blank=True)

    # Smart Khata (Customer Credit Score)
    credit_score = models.PositiveSmallIntegerField(
        default=50,
        help_text="Smart Khata credit score (0-100). Auto-updated based on payment behavior.",
    )
    last_payment_date = models.DateField(blank=True, null=True)
    average_payment_delay = models.IntegerField(
        default=0,
        help_text="Average payment delay (days). 0 means on-time/early on average.",
    )
    total_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Supplier specific fields
    credit_period = models.PositiveIntegerField(default=30, help_text="Credit period in days")
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Opening balance for supplier")
    is_active = models.BooleanField(default=True)
    customer_category = models.CharField(max_length=60, blank=True, null=True, help_text="Customer segment/category")

    # Helper / Computed Fields
    def get_payment_link(self):
        """Return a dynamic payment link if UPI & premium."""
        if self.upi_id and self.is_premium:
            name_encoded = self.name.replace(' ', '%20')
            return f"https://upi-pay-link-generator.com/pay?upi={self.upi_id}&name={name_encoded}&amount="
        return "Not available (Add UPI or upgrade to premium)"

    def total_credit(self):
        """Sum of all credit transactions for this party."""
        return self.transactions.filter(txn_type='credit').aggregate(total=Sum('amount'))['total'] or 0

    def total_debit(self):
        """Sum of all debit transactions for this party."""
        return self.transactions.filter(txn_type='debit').aggregate(total=Sum('amount'))['total'] or 0

    def balance(self):
        """Net balance (Credit - Debit)."""
        return self.total_credit() - self.total_debit()

    def __str__(self):
        return f"{self.name} ({self.party_type})"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Parties"


# ---------------- Secure Login Link ----------------
class LoginLink(models.Model):
    PURPOSE_CHOICES = (
        ("dashboard", "Dashboard Login"),
        ("payment", "Payment Link"),
        ("otp", "OTP Login"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_links"
    )
    token = models.CharField(max_length=64, unique=True, editable=False)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="dashboard")
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.is_active and timezone.now() <= self.expires_at

    def __str__(self):
        return f"{self.user_id} - {self.purpose} (active={self.is_active})"


# ---------------- Reminder Log ----------------
class ReminderLog(models.Model):
    REMINDER_TYPES = (
        ("due", "Due Reminder"),
        ("collector", "Collector Visit"),
        ("payment", "Payment Follow-up"),
        ("general", "General"),
    )
    CHANNELS = (
        ("whatsapp", "WhatsApp"),
        ("sms", "SMS"),
        ("email", "Email"),
    )
    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    )

    TONES = (
        ("friendly", "Friendly"),
        ("professional", "Professional"),
        ("strict", "Strict"),
    )

    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminder_logs"
    )
    invoice = models.ForeignKey(
        "commerce.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="khata_reminder_logs",
    )
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES, default="due")
    tone = models.CharField(max_length=20, choices=TONES, default="professional")
    channel = models.CharField(max_length=20, choices=CHANNELS, default="whatsapp")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    scheduled_for = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reminder_type} - {self.channel} - {self.status}"


# ---------------- Field Agent (Collector/Staff) ----------------
class FieldAgent(models.Model):
    ROLE_CHOICES = (
        ("collector", "Collector"),
        ("staff", "Staff"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_agents"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="field_agent_profile"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="collector")
    mobile = models.CharField(max_length=15, blank=True, null=True)
    assigned_parties = models.ManyToManyField(
        "khataapp.Party",
        related_name="assigned_agents",
        blank=True
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.role})"


# ---------------- Collector Visit ----------------
class CollectorVisit(models.Model):
    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("visited", "Visited"),
        ("not_available", "Not Available"),
        ("partial", "Partial"),
        ("cancelled", "Cancelled"),
    )

    agent = models.ForeignKey(
        FieldAgent,
        on_delete=models.CASCADE,
        related_name="visits"
    )
    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="collector_visits"
    )
    visit_date = models.DateField(default=timezone.now)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    collected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    payment_mode = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    proof = models.FileField(upload_to="collector_proofs/", blank=True, null=True)
    marked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def owner(self):
        return self.agent.owner

    def __str__(self):
        return f"{self.party.name} - {self.visit_date} ({self.status})"


# ---------------- Auto WhatsApp Login Link (Party) ----------------
@receiver(post_save, sender=Party)
def auto_create_login_link(sender, instance: Party, created, **kwargs):
    if not created:
        return

    mobile = instance.whatsapp_number or instance.mobile
    if not mobile:
        return

    User = get_user_model()
    user = User.objects.filter(mobile=instance.mobile).first()
    if not user:
        safe_email = f"{instance.mobile}@party.local" if instance.mobile else f"party{instance.id}@party.local"
        user = User.objects.filter(email__iexact=safe_email).first()
    if not user:
        user = User.objects.create(
            username=instance.name[:150],
            email=safe_email,
            mobile=instance.mobile,
            is_active=False,
            is_otp_verified=False
        )

    # Avoid duplicates: keep only one active dashboard link
    if LoginLink.objects.filter(user=user, purpose="dashboard", is_active=True).exists():
        return

    expires_at = timezone.now() + timedelta(days=7)
    link = LoginLink.objects.create(
        user=user,
        purpose="dashboard",
        expires_at=expires_at
    )

    # Queue WhatsApp message (offline queue)
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}"
    except Exception:
        base_url = ""

    url = f"{base_url}{reverse('accounts:login_link', args=[link.token])}"
    # Use a non-surrogate emoji escape to avoid UnicodeEncodeError in DB writes.
    message = f"Click here for more details \U0001F449 {url}"

    OfflineMessage.objects.create(
        party=instance,
        message=message,
        channel="whatsapp",
        status="pending"
    )


# ---------------- TRANSACTION MODEL ----------------
class Transaction(models.Model):

    TXN_TYPE_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    TXN_MODE_CHOICES = [
        ("cash", "Cash"),
        ("online", "Online"),
        ("upi", "UPI"),
        ("bank", "Bank Transfer"),
        ("cheque", "Cheque"),
    ]

    GST_TYPE_CHOICES = [
        ("gst", "GST"),
        ("nongst", "Non GST"),
    ]

    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    txn_type = models.CharField(max_length=10, choices=TXN_TYPE_CHOICES)
    txn_mode = models.CharField(max_length=20, choices=TXN_MODE_CHOICES, default="cash")

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    date = models.DateField()   # Manual date selection

    notes = models.TextField(blank=True, null=True)

    receipt = models.ImageField(upload_to="receipts/", blank=True, null=True)

    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_transactions"
    )

    payment = models.ForeignKey(
        "commerce.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_transactions"
    )

    voucher = models.ForeignKey(
        "commerce.SalesVoucher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions"
    )

    voucher_type = models.CharField(max_length=40, blank=True, null=True, db_index=True)

    invoice = models.ForeignKey(
        "commerce.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_khata_transactions",
    )

    gst_type = models.CharField(
        max_length=10,
        choices=GST_TYPE_CHOICES,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.party.name} - {self.txn_type.capitalize()} - ₹{self.amount}"

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Transactions"

# ✅ ---------------- Product Model ----------------
class Product(models.Model):
    """Simple product model for commerce compatibility"""
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, blank=True, null=True, unique=True)
    description = models.TextField(blank=True, null=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_products', null=True, blank=True)

    def __str__(self):
        return self.name


# ---------------- Company Settings ----------------
class CompanySettings(models.Model):
    company_name = models.CharField(max_length=100, default='My Business')
    default_plan = models.ForeignKey("billing.Plan", on_delete=models.SET_NULL, null=True, blank=True)
    whatsapp_api_key = models.CharField(max_length=255, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    sms_api_key = models.CharField(max_length=255, blank=True, null=True)
    sms_sender_number = models.CharField(max_length=20, blank=True, null=True)
    auto_sms_send = models.BooleanField(default=True)
    enable_auto_whatsapp = models.BooleanField(default=True)
    enable_monthly_email = models.BooleanField(default=True)
    def __str__(self):
        return self.company_name


# ---------------- Offline Message ----------------
class OfflineMessage(models.Model):
    CHANNEL_CHOICES = (("whatsapp", "WhatsApp"), ("sms", "SMS"))
    party = models.ForeignKey("Party", on_delete=models.SET_NULL, null=True, blank=True)
    recipient_name = models.CharField(max_length=120, blank=True, null=True)
    recipient_mobile = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"[{self.channel}] {self.message[:30]}... ({self.status})"


# ---------- Credit Grade Logic ----------
def compute_credit_grade(party: Party) -> str:
    totals = Transaction.objects.filter(party=party).values('txn_type').annotate(total=Sum('amount'))
    total_credit = sum(row['total'] for row in totals if row['txn_type'] == 'credit') or 0
    total_debit = sum(row['total'] for row in totals if row['txn_type'] == 'debit') or 0
    if total_credit == 0 and total_debit == 0:
        return 'D'
    ratio = (float(total_debit) / float(total_credit)) * 100 if total_credit > 0 else 0.0
    if ratio >= 90:
        return 'A+'
    elif ratio >= 70:
        return 'A'
    elif ratio >= 50:
        return 'B'
    elif ratio >= 30:
        return 'C'
    else:
        return 'D'


@receiver(post_save, sender=Transaction)
def update_party_grade_and_notify(sender, instance: Transaction, created, **kwargs):
    party = instance.party
    new_grade = compute_credit_grade(party)
    if party.credit_grade != new_grade:
        party.credit_grade = new_grade
        party.save(update_fields=['credit_grade'])
    if created and party.whatsapp_number:
        settings_obj = CompanySettings.objects.first()
        if settings_obj and settings_obj.enable_auto_whatsapp:
            msg = f"🧾 New {instance.txn_type.upper()} of ₹{instance.amount} added for {party.name}. Current grade: {party.credit_grade}"
            send_whatsapp_message(party.whatsapp_number.lstrip('+'), msg)


# ---------------- Report Schedule ----------------
class ReportSchedule(models.Model):
    send_date = models.DateField()
    send_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Report on {self.send_date} at {self.send_time}"


# ---------------- User Profile ----------------
class UserProfile(models.Model):
    SIGNUP_SOURCE = (("signup", "User Signup"), ("admin", "Created by Admin"))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="khata_profile")
    plan = models.ForeignKey("billing.Plan", on_delete=models.SET_NULL, null=True, blank=True, related_name='khata_userprofiles')
    full_name = models.CharField(max_length=255, blank=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True)
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=100, blank=True)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    created_from = models.CharField(max_length=20, choices=SIGNUP_SOURCE, default="signup")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.user.username} - {self.business_name or 'No Business'}"


# ---------------- Credit & Loan Models ----------------

class CreditSettings(models.Model):
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    penalty_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    apply_after_days = models.PositiveIntegerField(default=0)
    allow_partial_payment = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Credit Settings (Interest: {self.interest_rate}%, Penalty: {self.penalty_rate_percent}%)"


class CreditAccount(models.Model):
    party = models.ForeignKey("khataapp.Party", on_delete=models.CASCADE, related_name="credit_accounts")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def owner(self):
        return self.party.owner   # IMPORTANT

    @property
    def available(self):
        return self.credit_limit - self.outstanding

    def __str__(self):
        return f"{self.party.name} - {self.credit_limit}"


class CreditEntry(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
    )

    account = models.ForeignKey(
        CreditAccount,
        on_delete=models.CASCADE,
        related_name="entries"
    )

    txn_type = models.CharField(max_length=10, choices=(("credit", "Credit"), ("debit", "Debit")))
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(blank=True, null=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def party(self):
        return self.account.party

    @property
    def owner(self):
        return self.account.party.owner

    def __str__(self):
        return f"{self.account.party.name} - {self.txn_type} {self.amount}"


class EMI(models.Model):
    entry = models.ForeignKey(
        CreditEntry,
        on_delete=models.CASCADE,
        related_name="emis"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()

    paid = models.BooleanField(default=False)
    paid_on = models.DateField(blank=True, null=True)

    @property
    def party(self):
        return self.entry.account.party

    @property
    def owner(self):
        return self.entry.account.party.owner

    def mark_paid(self):
        self.paid = True
        self.paid_on = timezone.now().date()
        self.save()

    def __str__(self):
        return f"EMI of {self.amount} for {self.entry}"


class Penalty(models.Model):
    entry = models.ForeignKey(
        CreditEntry,
        on_delete=models.CASCADE,
        related_name="penalties"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    applied_at = models.DateTimeField(auto_now_add=True)

    @property
    def party(self):
        return self.entry.account.party

    @property
    def owner(self):
        return self.entry.account.party.owner

    def __str__(self):
        return f"Penalty {self.amount} - {self.reason}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    mobile = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_messages'
    )

    forwarded_to_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.mobile}"


# ---------------- SUPPLIER PAYMENT MODEL ----------------
class SupplierPayment(models.Model):
    PAYMENT_MODES = [
        ("cash", "Cash"),
        ("bank", "Bank Transfer"),
        ("upi", "UPI"),
        ("cheque", "Cheque"),
        ("card", "Card"),
    ]

    supplier = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="supplier_payments",
        limit_choices_to={'party_type': 'supplier'}
    )
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="supplier_payments",
        limit_choices_to={'order_type': 'PURCHASE'}
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default="cash")
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Cheque number, UPI ref, etc.")
    notes = models.TextField(blank=True, null=True)
    payment_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def owner(self):
        return self.supplier.owner

    def __str__(self):
        return f"Payment to {self.supplier.name} - ₹{self.amount} ({self.payment_mode})"


# ---------------- STOCK LEDGER MODEL (FIFO) ----------------
class StockLedger(models.Model):
    LEDGER_TYPE_CHOICES = [
        ("in", "Stock In"),
        ("out", "Stock Out"),
    ]

    product = models.ForeignKey("commerce.Product", on_delete=models.CASCADE, related_name="stock_ledgers")
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="stock_ledgers",
        help_text="Purchase order for stock in, Sale order for stock out"
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    ledger_type = models.CharField(max_length=3, choices=LEDGER_TYPE_CHOICES)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost price for purchases")
    remaining_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Remaining stock from this batch")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def owner(self):
        return self.order.owner

    def __str__(self):
        return f"{self.product.name} - {self.ledger_type.upper()} {self.quantity} @ ₹{self.unit_price}"

    class Meta:
        ordering = ['created_at']


# ---------------- CENTRAL BUSINESS ENGINE (BusinessGrowthEngine) ----------------
# Keep engine models in `khataapp/core_engine/` but register them under the `khataapp` app
# so migrations and backward-compatibility remain simple.
from .core_engine.models.engine import BusinessGrowthEngine  # noqa: E402,F401
from .core_engine.models.logs import EngineEventLog, RewardLedgerEntry  # noqa: E402,F401
from .core_engine.models.loyalty import LoyaltyAccount, LoyaltyLedgerEntry  # noqa: E402,F401
from .core_engine.models.referral import ReferralRecord  # noqa: E402,F401
from .core_engine.models.settings import EngineControlPanelSettings  # noqa: E402,F401
from .core_engine.models.tasks import DailyTaskCompletion, DailyTaskDefinition  # noqa: E402,F401

