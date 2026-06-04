from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, get_user_model, logout
from django.contrib.auth import get_backends
from django.db import transaction
from django.db.models import Sum, Q, Max
from django.core.paginator import Paginator, EmptyPage
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import Case, When, F, FloatField
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.conf import settings
from requests import request
from .models import DailySummary
from khataapp.models import Transaction
from django.utils.timezone import now
from datetime import timedelta
# accounts/views.py

from accounts.services.snapshot import build_business_snapshot
from .models import Expense, ExpenseCategory, LoyaltyPoints, LoyaltyProgram, MembershipTier, PointsTransaction, SpecialOffer
import uuid
import json
from khataapp.models import UserProfile as KhataProfile
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from billing.services import ensure_free_plan




# Accounts
from datetime import datetime, date, time
from .models import  OTP, LedgerEntry
from .utils import render_to_pdf_bytes
from .otp_delivery import send_otp_code
from .forms import SignupForm, AgentSignupForm, LoginForm, OTPForm, UserProfileForm

# External Models
from khataapp.models import Party, UserProfile, FieldAgent, CollectorVisit, LoginLink, CompanySettings, OfflineMessage, ReminderLog
from khataapp.utils.whatsapp_utils import send_whatsapp_message
from billing.models import Plan, Subscription
from billing.services import get_active_subscription, get_locked_feature_count, get_usage_summary
from commerce.models import Order, Payment, Invoice, Quotation
from django.db.utils import OperationalError, ProgrammingError
from commerce.models import Coupon, UserCoupon



User = get_user_model()
PARTY_SMART_KHATA_DEFER_FIELDS = (
    "credit_score",
    "last_payment_date",
    "average_payment_delay",
    "total_due",
)

def calculate_running_balance(entries):
    balance = 0

    for e in entries:
        amount = e.get("amount", 0)

        # Debit = positive
        # Credit = negative
        if amount > 0:
            e["debit"] = amount
            e["credit"] = 0
        else:
            e["debit"] = 0
            e["credit"] = abs(amount)

        # Running balance (Busy style)
        balance += amount
        e["balance"] = balance

    return entries
# ---------------------------------------------------
# WhatsApp Message URL Builder
# ---------------------------------------------------
def whatsapp_message_url(mobile, text):
    import urllib.parse
    return f"https://wa.me/91{mobile}?text={urllib.parse.quote(text)}"


# ---------------------------------------------------
def can_manage_billing_hierarchy(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        return user.groups.filter(name__in=["Admin", "Super Admin"]).exists()
    except Exception:
        return False


def can_manage_linked_users(user) -> bool:
    # Same gating as billing linked-user management.
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        if user.groups.filter(name__in=["Admin", "Super Admin"]).exists():
            return True
    except Exception:
        pass
    try:
        return bool(user.has_permission("billing.user.manage_subusers"))
    except Exception:
        return False

# Role Resolution
# ---------------------------------------------------
def resolve_user_role(user):
    if not user:
        return "party"

    if user.is_superuser or user.is_staff:
        return "owner"

    agent = getattr(user, "field_agent_profile", None)
    if agent and agent.is_active:
        return "collector" if agent.role == "collector" else "staff"

    # Group-based roles (seeded by management commands)
    # If someone is in the "agent" group but has no active FieldAgent profile,
    # do NOT route them into the collector dashboard (prevents redirect loops).
    if user.groups.filter(name__iexact="agent").exists():
        return "party"
    if user.groups.filter(name__iexact="staff").exists():
        return "staff"

    # Party/customer-style accounts (read-only views)
    if user.groups.filter(name__iexact="party").exists():
        return "party"
    if user.groups.filter(name__iexact="customer").exists():
        return "party"
    if user.groups.filter(name__iexact="supplier").exists():
        return "party"
    if user.groups.filter(name__iexact="vendor").exists():
        return "party"

    # Legacy heuristic: party accounts often use a local email domain.
    try:
        email = (user.email or "").strip().lower()
        if email.endswith("@party.local"):
            return "party"
    except Exception:
        pass

    # Safety default for desktop: treat unknown users as owners so signup/login isn't blocked.
    return "owner"


def role_based_redirect(user):
    role = resolve_user_role(user)
    if role == "owner":
        return redirect("accounts:dashboard")
    if role == "collector":
        return redirect("accounts:collector_dashboard")
    if role == "staff":
        return redirect("accounts:staff_dashboard")
    return redirect("accounts:customer_dashboard")

def users_list(request):
    admin_users = User.objects.filter(is_staff=True)  # admin users
    signup_users = User.objects.filter(is_staff=False)  # users created from signup
    profiles = UserProfile.objects.all()  # profile data if needed

    context = {
        "admin_users": admin_users,
        "signup_users": signup_users,
        "profiles": profiles,
    }
    return render(request, "accounts/users_list.html", context)

# ----------------- DASHBOARD -----------------
@xframe_options_exempt
@login_required
def dashboard(request):
    user = request.user

    # ====
    # PERIOD FILTER
    # ====
    period = request.GET.get("period", "today")
    today = now().date()

    if period == "yesterday":
        selected_date = today - timedelta(days=1)
    elif period == "month":
        selected_date = today.replace(day=1)
    else:
        selected_date = today

    # ====
    # BUSINESS SNAPSHOT
    # ====
    snapshot = build_business_snapshot(user, selected_date)

    # ====
    # GREETING
    # ====
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"

    # ====
    # PROFILE
    # ====
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ====
    # DAILY SUMMARY
    # ====
    summary = update_daily_summary(user)

    # ====
    # RECENT DATA
    # ====
    recent_parties = (
        Party.objects.filter(owner=user)
        .defer(*PARTY_SMART_KHATA_DEFER_FIELDS)
        .order_by("-id")[:50]
    )
    recent_transactions = Transaction.objects.filter(
        party__owner=user
    ).order_by("-id")[:50]

    # ====
    # OVERALL TOTALS
    # ====
    total_credit_all = Transaction.objects.filter(
        party__owner=user, txn_type="credit"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    total_debit_all = Transaction.objects.filter(
        party__owner=user, txn_type="debit"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    net_balance = total_debit_all - total_credit_all

    # ====
    # PARTY CARDS
    # ====
    party_cards = []
    parties = (
        Party.objects.filter(owner=user)
        .defer(*PARTY_SMART_KHATA_DEFER_FIELDS)
        .order_by("name")
    )

    decimal_zero = Decimal("0.00")

    # Avoid N+1 aggregation queries per party (dashboard can become very slow with many parties).
    txn_totals = (
        Transaction.objects.filter(party__owner=user)
        .values("party_id", "txn_type")
        .annotate(total=Sum("amount"))
    )
    cash_credit_by_party = {}
    cash_debit_by_party = {}
    for r in txn_totals:
        party_id = r.get("party_id")
        total = r.get("total") or decimal_zero
        if r.get("txn_type") == "credit":
            cash_credit_by_party[party_id] = total
        else:
            cash_debit_by_party[party_id] = total

    invoice_total_by_party = {
        r["order__party_id"]: (r["total"] or decimal_zero)
        for r in Invoice.objects.filter(order__party__owner=user)
        .values("order__party_id")
        .annotate(total=Sum("amount"))
    }

    payment_total_by_party = {
        r["invoice__order__party_id"]: (r["total"] or decimal_zero)
        for r in Payment.objects.filter(invoice__order__party__owner=user)
        .values("invoice__order__party_id")
        .annotate(total=Sum("amount"))
    }

    for party in parties:

        party_cash_credit = cash_credit_by_party.get(party.id, decimal_zero)
        party_cash_debit = cash_debit_by_party.get(party.id, decimal_zero)
        invoice_total = invoice_total_by_party.get(party.id, decimal_zero)
        payment_total = payment_total_by_party.get(party.id, decimal_zero)

        total_debit = invoice_total + party_cash_debit
        total_credit = payment_total + party_cash_credit

        balance = total_debit - total_credit   # 👈 yaha balance define kiya

        party_cards.append({
            "party": party,
            "total_debit": total_debit,     # ✅ correct variable
            "total_credit": total_credit,   # ✅ correct variable
            "balance": balance,             # ✅ correct variable
        })

    # ====
    # COUPONS
    # ====
    active_coupons = Coupon.objects.filter(
        is_active=True
    ).order_by("-created_at")[:10]

    user_coupons = UserCoupon.objects.filter(
        user=user
    ).select_related("coupon")

    # ====
    # SUBSCRIPTION & FEATURES
    # ====
    subscription = get_active_subscription(user)
    locked_features_count = get_locked_feature_count(user)
    usage_summary = get_usage_summary(user)

    # ====
    # COMMERCE: QUOTATIONS
    # ====
    try:
        quotation_total = Quotation.objects.filter(party__owner=user).count()
        quotation_pending_approval = Quotation.objects.filter(party__owner=user, status=Quotation.Status.VERIFIED).count()
        quotation_converted = Quotation.objects.filter(party__owner=user, status=Quotation.Status.CONVERTED).count()
        quotation_rejected = Quotation.objects.filter(party__owner=user, status=Quotation.Status.REJECTED).count()
    except (OperationalError, ProgrammingError):
        # Migrations may not be applied yet (e.g., fresh DB). Keep dashboard functional.
        quotation_total = 0
        quotation_pending_approval = 0
        quotation_converted = 0
        quotation_rejected = 0

    # ====
    # SMART KHATA: HIGH DUE CUSTOMERS (Widget)
    # ====
    high_due_customers = []
    try:
        high_due_qs = (
            Party.objects.filter(owner=user, party_type="customer", total_due__gt=0)
            .order_by("-total_due", "name", "id")[:5]
        )
        last_sent_map = {
            row["party_id"]: row["last_sent"]
            for row in ReminderLog.objects.filter(party__in=high_due_qs, status="sent")
            .values("party_id")
            .annotate(last_sent=Max("sent_at"))
        }
        for c in high_due_qs:
            high_due_customers.append(
                {
                    "party": c,
                    "due": getattr(c, "total_due", 0) or 0,
                    "credit_score": int(getattr(c, "credit_score", 0) or 0),
                    "last_reminder_sent": last_sent_map.get(c.id),
                }
            )
    except Exception:
        high_due_customers = []

    # ====
    # SMART BI: Business Health Meter (lazy daily compute)
    # ====
    business_health = None
    business_health_level = None
    try:
        from smart_bi.services.business_health import health_level as _health_level, upsert_business_metric

        business_health = upsert_business_metric(user, day=timezone.localdate())
        business_health_level = _health_level(getattr(business_health, "health_score", 0) or 0)
    except Exception:
        business_health = None
        business_health_level = None

    duplicate_invoice_alerts = []
    try:
        from smart_bi.models import DuplicateInvoiceLog

        duplicate_invoice_alerts = list(
            DuplicateInvoiceLog.objects.select_related(
                "invoice",
                "invoice__order",
                "invoice__order__party",
                "possible_duplicate",
                "possible_duplicate__order",
                "possible_duplicate__order__party",
            )
            .filter(owner=user)
            .order_by("-created_at", "-id")[:5]
        )
    except Exception:
        duplicate_invoice_alerts = []

    demo_output_state = None
    is_demo_test3_dashboard = False
    try:
        demo_identity = " ".join(
            [
                str(getattr(user, "username", "") or ""),
                str(getattr(user, "email", "") or ""),
                str(getattr(profile, "full_name", "") or ""),
            ]
        ).lower().replace(" ", "")
        is_demo_test3_dashboard = "demotest3" in demo_identity or "demotest3" in demo_identity.replace(".", "")
        if is_demo_test3_dashboard:
            from addons.demo_center.services import get_user_state

            demo_output_state = get_user_state(user)
    except Exception:
        demo_output_state = None
        is_demo_test3_dashboard = False

    # ====
    # CONTEXT
    # ====
    context = {
        "user": user,
        "profile": profile,
        "recent_parties": recent_parties,
        "recent_transactions": recent_transactions,
        "total_credit": total_credit_all,
        "total_debit": total_debit_all,
        "net_balance": net_balance,
        "party_cards": party_cards,
        "summary": summary,
        "snapshot": snapshot,
        "period": period,
        "greeting": greeting,
        "subscription": subscription,
        "locked_features_count": locked_features_count,
        "usage_summary": usage_summary,
        "quotation_total": quotation_total,
        "quotation_pending_approval": quotation_pending_approval,
        "quotation_converted": quotation_converted,
        "quotation_rejected": quotation_rejected,
        "high_due_customers": high_due_customers,
        "business_health": business_health,
        "business_health_level": business_health_level,
        "duplicate_invoice_alerts": duplicate_invoice_alerts,
        "is_demo_test3_dashboard": is_demo_test3_dashboard,
        "demo_output_state": demo_output_state,
    }

    return render(request, "accounts/dashboard.html", context)




# ---------------------------------------------------
# Role Dashboard Router
# ---------------------------------------------------
@login_required
def role_dashboard(request):
    return role_based_redirect(request.user)

# -----------------------------------------
# Party ledger: main view (with filters)
# -----------------------------------------
# --- SUMMARY FUNCTION FOR DASHBOARD ---
def get_party_summary(party):
    orders = Order.objects.filter(party=party)
    invoices = Invoice.objects.filter(order__party=party)
    payments = Payment.objects.filter(invoice__order__party=party)
    txns = Transaction.objects.filter(party=party)

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    # Orders
    for o in orders:
        amount = o.total_amount() if hasattr(o, "total_amount") else Decimal("0.00")
        total_debit += amount

    # Invoices
    for inv in invoices:
        total_debit += inv.amount

    # Payments
    for p in payments:
        total_credit += p.amount

    # Manual Txns
    for t in txns:
        if t.txn_type == "debit":
            total_debit += t.amount
        else:
            total_credit += t.amount

    balance = total_debit - total_credit

    return {
        "debit": total_debit,
        "credit": total_credit,
        "balance": balance,
    }

# ---------------------------------------------------
# Helper to normalize dates
# ---------------------------------------------------
def normalize_date(d):
    # If already date, return
    if isinstance(d, date) and not isinstance(d, datetime):
        return d

    # If datetime, convert to date
    if isinstance(d, datetime):
        return d.date()

    # If string, convert safely
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except:
        try:
            return datetime.strptime(d, "%Y-%m-%d %H:%M:%S").date()
        except:
            return date.today()  # fallback)

# ---------------------------------------------------
# Party Ledger (Busy-Style with Running Balance)
# ---------------------------------------------------
def _parse_iso_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    # First try Django's parser (handles YYYY-MM-DD reliably)
    try:
        d = parse_date(value)
        if d:
            return d
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


def _dt_range_for_dates(date_from: date | None, date_to: date | None):
    """
    Convert date range to datetime range for filtering DateTimeField safely.

    Uses [start, end) where end is next-day midnight to avoid DB date-cast issues.
    """
    if not date_from and not date_to:
        return (None, None)

    tz = None
    try:
        tz = timezone.get_current_timezone()
    except Exception:
        tz = None

    start_dt = None
    end_dt = None
    if date_from:
        start_dt = datetime.combine(date_from, time.min)
        try:
            if timezone.is_naive(start_dt) and getattr(timezone, "make_aware", None) and tz:
                start_dt = timezone.make_aware(start_dt, tz)
        except Exception:
            pass
    if date_to:
        # exclusive end: next day 00:00
        end_dt = datetime.combine(date_to + timedelta(days=1), time.min)
        try:
            if timezone.is_naive(end_dt) and getattr(timezone, "make_aware", None) and tz:
                end_dt = timezone.make_aware(end_dt, tz)
        except Exception:
            pass
    return (start_dt, end_dt)


def _build_party_ledger_entries(
    *,
    party: Party,
    date_from: date | None,
    date_to: date | None,
    invoice_contains: str = "",
) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    """
    Build Busy-style party ledger rows with a running balance.

    Running balance is computed as: opening_balance + Σ(credit - debit)
    so it stays correct even when filtering by date range.
    """
    invoice_contains = (invoice_contains or "").strip()

    has_party_ledger_entries = False
    try:
        has_party_ledger_entries = LedgerEntry.objects.filter(party=party).exists()
    except Exception:
        has_party_ledger_entries = False

    if has_party_ledger_entries:
        base_qs = LedgerEntry.objects.filter(party=party).order_by("date", "id").only(
            "date",
            "txn_type",
            "amount",
            "invoice_no",
            "description",
            "credit",
            "debit",
            "notes",
            "source",
        )
        if invoice_contains:
            base_qs = base_qs.filter(invoice_no__icontains=invoice_contains)
    else:
        # Fallback to real Transactions (common in older datasets where PartyLedgerEntry was not posted).
        base_qs = Transaction.objects.filter(party=party).order_by("date", "id").only(
            "id",
            "date",
            "txn_type",
            "amount",
            "notes",
            "invoice_id",
            "payment_id",
            "order_id",
            "created_at",
        )
        try:
            base_qs = base_qs.filter(is_deleted=False)
        except Exception:
            pass

    opening_balance = Decimal("0.00")
    start_dt, end_dt = (None, None)
    if has_party_ledger_entries:
        start_dt, end_dt = _dt_range_for_dates(date_from, date_to)

    if date_from:
        if has_party_ledger_entries:
            opening_filter_dt = start_dt or datetime.combine(date_from, time.min)
            opening_totals = LedgerEntry.objects.filter(party=party, date__lt=opening_filter_dt).aggregate(
                c=Sum("credit"),
                d=Sum("debit"),
            )
            opening_credit = opening_totals.get("c") or Decimal("0.00")
            opening_debit = opening_totals.get("d") or Decimal("0.00")
            opening_balance = opening_credit - opening_debit
        else:
            opening_totals = Transaction.objects.filter(party=party, date__lt=date_from).aggregate(
                c=Sum(Case(When(txn_type="credit", then=F("amount")), default=0, output_field=FloatField())),
                d=Sum(Case(When(txn_type="debit", then=F("amount")), default=0, output_field=FloatField())),
            )
            opening_credit = Decimal(str(opening_totals.get("c") or 0))
            opening_debit = Decimal(str(opening_totals.get("d") or 0))
            opening_balance = opening_credit - opening_debit

    if date_from:
        if has_party_ledger_entries:
            if start_dt:
                base_qs = base_qs.filter(date__gte=start_dt)
        else:
            base_qs = base_qs.filter(date__gte=date_from)
    if date_to:
        if has_party_ledger_entries:
            if end_dt:
                base_qs = base_qs.filter(date__lt=end_dt)
        else:
            base_qs = base_qs.filter(date__lte=date_to)

    if invoice_contains and not has_party_ledger_entries:
        # Keep transaction rows; invoice matching will be applied when we build merged rows below.
        pass

    rows: list[dict] = []
    total_credit = Decimal("0.00")
    total_debit = Decimal("0.00")
    running = opening_balance

    if not has_party_ledger_entries:
        # Merge Transaction + Invoice + Payment into one timeline (best-effort).
        try:
            invoice_qs = Invoice.objects.filter(order__party=party).order_by("created_at", "id").only(
                "id",
                "number",
                "amount",
                "status",
                "created_at",
            )
        except Exception:
            invoice_qs = Invoice.objects.none()

        try:
            payment_qs = Payment.objects.filter(invoice__order__party=party).order_by("created_at", "id").only(
                "id",
                "amount",
                "method",
                "reference",
                "note",
                "created_at",
                "invoice_id",
            )
        except Exception:
            payment_qs = Payment.objects.none()

        # Optional invoice filter (matches invoice number).
        if invoice_contains:
            try:
                invoice_qs = invoice_qs.filter(number__icontains=invoice_contains)
                payment_qs = payment_qs.filter(invoice__number__icontains=invoice_contains)
            except Exception:
                pass

        start_dt, end_dt = _dt_range_for_dates(date_from, date_to)
        payment_ids = set()
        payment_signatures = set()
        payment_party_day_signatures = set()
        payment_ref_tokens = set()
        try:
            for pay_ref in payment_qs:
                pay_amount = Decimal(str(getattr(pay_ref, "amount", 0) or 0)).quantize(Decimal("0.01"))
                pay_dt = getattr(pay_ref, "created_at", None)
                pay_day = pay_dt.date() if hasattr(pay_dt, "date") else None
                pay_ref_text = (getattr(pay_ref, "reference", "") or "").strip().lower()
                payment_ids.add(getattr(pay_ref, "id", None))
                payment_signatures.add((getattr(pay_ref, "invoice_id", None), pay_amount))
                payment_party_day_signatures.add((party.id, pay_day, pay_amount))
                if pay_ref_text:
                    payment_ref_tokens.add(pay_ref_text)
        except Exception:
            payment_ids = set()
            payment_signatures = set()
            payment_party_day_signatures = set()
            payment_ref_tokens = set()

        def _is_duplicate_payment_mirror(txn) -> bool:
            if getattr(txn, "txn_type", "") != "credit":
                return False
            txn_amount = Decimal(str(getattr(txn, "amount", 0) or 0)).quantize(Decimal("0.01"))
            txn_invoice_id = getattr(txn, "invoice_id", None)
            if getattr(txn, "payment_id", None) in payment_ids:
                return True
            if txn_invoice_id and (txn_invoice_id, txn_amount) in payment_signatures:
                return True
            txn_day = getattr(txn, "date", None)
            if (party.id, txn_day, txn_amount) in payment_party_day_signatures:
                notes_l = (getattr(txn, "notes", "") or "").lower()
                voucher_l = (getattr(txn, "voucher_type", "") or "").lower()
                if (
                    getattr(txn, "order_id", None)
                    or "pos" in notes_l
                    or "invoice" in notes_l
                    or "payment" in notes_l
                    or voucher_l in {"pos", "pos_sale", "invoice_payment", "auto_payment"}
                    or any(token and token in notes_l for token in payment_ref_tokens)
                ):
                    return True
            return False

        merged = []
        # Transactions: use created_at if present else date at midnight.
        for t in base_qs.select_related("invoice", "order", "order__invoice"):
            txn_amount = Decimal(str(t.amount or 0)).quantize(Decimal("0.01"))
            if _is_duplicate_payment_mirror(t):
                continue
            dt_val = None
            try:
                dt_val = getattr(t, "created_at", None)
            except Exception:
                dt_val = None
            if not dt_val:
                try:
                    dt_val = datetime.combine(t.date, time.min)
                except Exception:
                    dt_val = None

            inv_no = ""
            try:
                inv = getattr(t, "invoice", None)
                if inv and getattr(inv, "number", None):
                    inv_no = inv.number
                else:
                    ord_obj = getattr(t, "order", None)
                    inv2 = getattr(ord_obj, "invoice", None) if ord_obj else None
                    if inv2 and getattr(inv2, "number", None):
                        inv_no = inv2.number
            except Exception:
                inv_no = ""

            if invoice_contains and invoice_contains.lower() not in (inv_no or "").lower():
                continue

            merged.append(
                {
                    "dt": dt_val,
                    "source": "transaction",
                    "txn_type": t.txn_type,
                    "amount": txn_amount,
                    "invoice_no": inv_no,
                    "description": getattr(t, "notes", "") or "Transaction",
                    "id": getattr(t, "id", 0) or 0,
                }
            )

        for inv in invoice_qs:
            merged.append(
                {
                    "dt": getattr(inv, "created_at", None) or datetime.combine(getattr(inv, "created_at", timezone.now()).date(), time.min),
                    "source": "invoice",
                    "txn_type": "debit",
                    "amount": Decimal(str(getattr(inv, "amount", 0) or 0)),
                    "invoice_no": getattr(inv, "number", "") or "",
                    "description": f"Invoice ({getattr(inv, 'status', '')})",
                    "id": getattr(inv, "id", 0) or 0,
                }
            )

        for pay in payment_qs.select_related("invoice"):
            inv_no = ""
            try:
                inv_no = getattr(getattr(pay, "invoice", None), "number", "") or ""
            except Exception:
                inv_no = ""
            note = getattr(pay, "note", "") or getattr(pay, "method", "") or "Payment"
            merged.append(
                {
                    "dt": getattr(pay, "created_at", None) or timezone.now(),
                    "source": "payment",
                    "txn_type": "credit",
                    "amount": Decimal(str(getattr(pay, "amount", 0) or 0)),
                    "invoice_no": inv_no,
                    "description": note,
                    "id": getattr(pay, "id", 0) or 0,
                }
            )

        # Filter by datetime window if provided
        if start_dt:
            merged = [m for m in merged if m.get("dt") and m["dt"] >= start_dt]
        if end_dt:
            merged = [m for m in merged if m.get("dt") and m["dt"] < end_dt]

        merged.sort(key=lambda m: (m.get("dt") or timezone.now(), m.get("id") or 0))

        # Opening balance (before start_dt)
        opening_balance = Decimal("0.00")
        if start_dt:
            opening_rows = []
            # Recompute opening rows using unfiltered merged data for correctness
            all_merged = []
            for t in base_qs.select_related("invoice", "order", "order__invoice"):
                txn_amount = Decimal(str(t.amount or 0)).quantize(Decimal("0.01"))
                if _is_duplicate_payment_mirror(t):
                    continue
                dt_val = getattr(t, "created_at", None) or datetime.combine(t.date, time.min)
                if invoice_contains:
                    inv_no = ""
                    try:
                        inv = getattr(t, "invoice", None)
                        if inv and getattr(inv, "number", None):
                            inv_no = inv.number
                        else:
                            ord_obj = getattr(t, "order", None)
                            inv2 = getattr(ord_obj, "invoice", None) if ord_obj else None
                            if inv2 and getattr(inv2, "number", None):
                                inv_no = inv2.number
                    except Exception:
                        inv_no = ""
                    if invoice_contains.lower() not in (inv_no or "").lower():
                        continue
                all_merged.append({"dt": dt_val, "txn_type": t.txn_type, "amount": txn_amount})
            for inv in invoice_qs:
                all_merged.append({"dt": getattr(inv, "created_at", None), "txn_type": "debit", "amount": Decimal(str(getattr(inv, "amount", 0) or 0))})
            for pay in payment_qs:
                all_merged.append({"dt": getattr(pay, "created_at", None), "txn_type": "credit", "amount": Decimal(str(getattr(pay, "amount", 0) or 0))})
            for m in all_merged:
                if m.get("dt") and m["dt"] < start_dt:
                    opening_rows.append(m)
            for m in opening_rows:
                amt = m.get("amount") or Decimal("0.00")
                if (m.get("txn_type") or "") == "credit":
                    opening_balance += amt
                else:
                    opening_balance -= amt

        # Now build rows with running
        running = opening_balance
        total_credit = Decimal("0.00")
        total_debit = Decimal("0.00")
        rows = []
        for m in merged:
            amt = m.get("amount") or Decimal("0.00")
            txn_type = m.get("txn_type") or ""
            credit = amt if txn_type == "credit" else Decimal("0.00")
            debit = amt if txn_type == "debit" else Decimal("0.00")
            total_credit += credit
            total_debit += debit
            running += credit - debit
            rows.append(
                {
                    "date": m.get("dt"),
                    "source": m.get("source"),
                    "txn_type": txn_type,
                    "amount": amt,
                    "invoice_no": m.get("invoice_no") or "",
                    "description": m.get("description") or "",
                    "notes": m.get("notes") or "",
                    "credit": credit,
                    "debit": debit,
                    "balance": running,
                    "party": party,
                }
            )

        rows.reverse()
        closing_balance = running
        return rows, total_credit, total_debit, closing_balance

    for e in base_qs:
        if has_party_ledger_entries:
            credit = e.credit or Decimal("0.00")
            debit = e.debit or Decimal("0.00")
            invoice_no = e.invoice_no
            description = e.description or e.notes or ""
            source = e.source
            entry_date = e.date
            amount = e.amount
            txn_type = e.txn_type
        else:
            amount = Decimal(str(getattr(e, "amount", 0) or 0))
            txn_type = getattr(e, "txn_type", "") or ""
            credit = amount if txn_type == "credit" else Decimal("0.00")
            debit = amount if txn_type == "debit" else Decimal("0.00")
            invoice_no = ""
            try:
                inv = getattr(e, "invoice", None)
                if inv and getattr(inv, "number", None):
                    invoice_no = inv.number
                else:
                    ord_obj = getattr(e, "order", None)
                    inv2 = getattr(ord_obj, "invoice", None) if ord_obj else None
                    if inv2 and getattr(inv2, "number", None):
                        invoice_no = inv2.number
            except Exception:
                invoice_no = ""
            description = getattr(e, "notes", "") or "Transaction"
            source = "transaction"
            entry_date = getattr(e, "date", None)

        total_credit += credit
        total_debit += debit
        running += credit - debit

        rows.append(
            {
                "date": entry_date,
                "source": source,
                "txn_type": txn_type,
                "amount": amount,
                "invoice_no": invoice_no,
                "description": description,
                "notes": getattr(e, "notes", "") if not has_party_ledger_entries else (e.notes or ""),
                "credit": credit,
                "debit": debit,
                "balance": running,
                "party": party,
            }
        )

    rows.reverse()  # newest first for UI
    closing_balance = running
    return rows, total_credit, total_debit, closing_balance


@login_required
def party_ledger(request, party_id):

    party = get_object_or_404(Party, id=party_id, owner=request.user)

    date_from_raw = request.GET.get("from")
    date_to_raw = request.GET.get("to")
    invoice = (request.GET.get("invoice") or "").strip()
    date_from = _parse_iso_date(date_from_raw)
    date_to = _parse_iso_date(date_to_raw)

    all_rows, total_credit, total_debit, closing_balance = _build_party_ledger_entries(
        party=party,
        date_from=date_from,
        date_to=date_to,
        invoice_contains=invoice,
    )

    paginator = Paginator(all_rows, 20)
    page = int(request.GET.get("page", 1))
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # --------------------------
    # CONTEXT
    # --------------------------
    context = {
        "party": party,
        "entries": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balance": closing_balance,
        "whatsapp_url": whatsapp_message_url(
            party.mobile,
            f"Your current balance is ₹{closing_balance}"
        ),
    }

    return render(request, "accounts/party_ledger.html", context)

@login_required
def ledger_list(request):
    parties = (
        Party.objects.filter(owner=request.user)
        .defer(*PARTY_SMART_KHATA_DEFER_FIELDS)
        .order_by("name")
    )

    selected_party = (request.GET.get("party") or "").strip()
    from_date = (request.GET.get("from_date") or "").strip()
    to_date = (request.GET.get("to_date") or "").strip()
    invoice = (request.GET.get("invoice") or "").strip()

    qs = LedgerEntry.objects.filter(party__owner=request.user).select_related("party").order_by("-date", "-id")

    party_obj = None
    if selected_party:
        party_obj = (
            Party.objects.filter(id=selected_party, owner=request.user)
            .defer(*PARTY_SMART_KHATA_DEFER_FIELDS)
            .first()
        )
        if not party_obj:
            return HttpResponseForbidden("You do not have permission to view this party.")
        qs = qs.filter(party=party_obj)

    # If the party ledger table is empty (common in older datasets), use Transactions fallback for selected party.
    use_txn_fallback = False
    if party_obj:
        try:
            use_txn_fallback = not LedgerEntry.objects.filter(party=party_obj).exists()
        except Exception:
            use_txn_fallback = False

    date_from = _parse_iso_date(from_date)
    date_to = _parse_iso_date(to_date)

    if party_obj and use_txn_fallback:
        rows, total_credit_d, total_debit_d, closing_balance_d = _build_party_ledger_entries(
            party=party_obj,
            date_from=date_from,
            date_to=date_to,
            invoice_contains=invoice,
        )

        paginator = Paginator(rows, 25)
        page_number = request.GET.get("page", 1)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        whatsapp_url = whatsapp_message_url(
            party_obj.mobile,
            f"Your current balance is ₹{closing_balance_d}",
        )

        pdf_download_url = reverse("accounts:party_ledger_pdf", args=[party_obj.id]) + (
            f"?from={from_date}&to={to_date}&invoice={invoice}"
        )
        pdf_print_url = pdf_download_url + "&inline=1"

        closing_balance_abs = float(abs(closing_balance_d))
        closing_balance_kind = "CR" if closing_balance_d > 0 else ("DR" if closing_balance_d < 0 else "")

        return render(
            request,
            "accounts/ledger_list.html",
            {
                "parties": parties,
                "party": party_obj,
                "entries": page_obj.object_list,
                "page_obj": page_obj,
                "selected_party": selected_party,
                "from_date": from_date,
                "to_date": to_date,
                "invoice": invoice,
                "totals": {
                    "total_debit": float(total_debit_d),
                    "total_credit": float(total_credit_d),
                    "balance": float(closing_balance_d),
                },
                "closing_balance": float(closing_balance_d),
                "closing_balance_abs": closing_balance_abs,
                "closing_balance_kind": closing_balance_kind,
                "party_cards": [],
                "whatsapp_url": whatsapp_url,
                "pdf_download_url": pdf_download_url,
                "pdf_print_url": pdf_print_url,
            },
        )

    # Normal LedgerEntry path
    if from_date:
        if date_from:
            start_dt, end_dt = _dt_range_for_dates(date_from, None)
            if start_dt:
                qs = qs.filter(date__gte=start_dt)
        else:
            from_date = ""

    if to_date:
        if date_to:
            start_dt, end_dt = _dt_range_for_dates(None, date_to)
            if end_dt:
                qs = qs.filter(date__lt=end_dt)
        else:
            to_date = ""

    if invoice:
        qs = qs.filter(invoice_no__icontains=invoice)

    totals = qs.aggregate(
        total_debit=Sum(Case(When(txn_type="debit", then=F("amount")), default=0, output_field=FloatField())),
        total_credit=Sum(Case(When(txn_type="credit", then=F("amount")), default=0, output_field=FloatField())),
    )
    total_debit = float(totals.get("total_debit") or 0)
    total_credit = float(totals.get("total_credit") or 0)
    closing_balance = total_credit - total_debit
    closing_balance_abs = abs(closing_balance)
    closing_balance_kind = "CR" if closing_balance > 0 else ("DR" if closing_balance < 0 else "")

    whatsapp_url = ""
    pdf_download_url = ""
    pdf_print_url = ""
    if party_obj:
        whatsapp_url = whatsapp_message_url(
            party_obj.mobile,
            f"Your current balance is ₹{closing_balance}",
        )
        pdf_download_url = reverse("accounts:party_ledger_pdf", args=[party_obj.id]) + (
            f"?from={from_date}&to={to_date}&invoice={invoice}"
        )
        pdf_print_url = pdf_download_url + "&inline=1"

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    party_cards = []
    if not selected_party:
        # Summaries for quick navigation (Busy/Tally style).
        for p in parties:
            has_entries = False
            try:
                has_entries = LedgerEntry.objects.filter(party=p).exists()
            except Exception:
                has_entries = False

            if has_entries:
                p_qs = LedgerEntry.objects.filter(party=p).order_by("-date", "-id")
                p_tot = p_qs.aggregate(
                    total_debit=Sum(Case(When(txn_type="debit", then=F("amount")), default=0, output_field=FloatField())),
                    total_credit=Sum(Case(When(txn_type="credit", then=F("amount")), default=0, output_field=FloatField())),
                )
                p_debit = float(p_tot.get("total_debit") or 0)
                p_credit = float(p_tot.get("total_credit") or 0)
                recent = list(p_qs.select_related("party")[:3])
            else:
                t_qs = Transaction.objects.filter(party=p)
                try:
                    t_qs = t_qs.filter(is_deleted=False)
                except Exception:
                    pass
                t_tot = t_qs.aggregate(
                    total_debit=Sum(Case(When(txn_type="debit", then=F("amount")), default=0, output_field=FloatField())),
                    total_credit=Sum(Case(When(txn_type="credit", then=F("amount")), default=0, output_field=FloatField())),
                )
                p_debit = float(t_tot.get("total_debit") or 0)
                p_credit = float(t_tot.get("total_credit") or 0)
                recent = list(t_qs.select_related("party").order_by("-date", "-id")[:3])
            party_cards.append(
                {
                    "party": p,
                    "total_debit": p_debit,
                    "total_credit": p_credit,
                    "balance": p_credit - p_debit,
                    "recent": recent,
                }
            )

    return render(
        request,
        "accounts/ledger_list.html",
        {
            "parties": parties,
            "party": party_obj,
            "entries": page_obj.object_list,
            "page_obj": page_obj,
            "selected_party": selected_party,
            "from_date": from_date,
            "to_date": to_date,
            "invoice": invoice,
            "totals": {"total_debit": total_debit, "total_credit": total_credit, "balance": closing_balance},
            "closing_balance": closing_balance,
            "closing_balance_abs": closing_balance_abs,
            "closing_balance_kind": closing_balance_kind,
            "party_cards": party_cards,
            "whatsapp_url": whatsapp_url,
            "pdf_download_url": pdf_download_url,
            "pdf_print_url": pdf_print_url,
        },
    )

#---------------------------------------------------
# AJAX Load More (Busy style)
# ---------------------------------------------------
@login_required
def party_ledger_load_more(request, party_id):

    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({"error": "Only AJAX allowed"}, status=400)

    party = get_object_or_404(Party, id=party_id, owner=request.user)

    date_from = _parse_iso_date(request.GET.get("from"))
    date_to = _parse_iso_date(request.GET.get("to"))

    all_rows, _, _, _ = _build_party_ledger_entries(
        party=party,
        date_from=date_from,
        date_to=date_to,
    )


@login_required
def ledger_ui(request):
    """
    UI wrapper for party ledger.

    Accepts query params:
    - party=<id>
    - from_date / to_date (or from / to)
    - invoice=<text> (optional)
    """
    selected_party = (request.GET.get("party") or "").strip()
    if not selected_party:
        return redirect("accounts:ledger_list")

    party = get_object_or_404(Party, id=int(selected_party), owner=request.user)

    from_date_raw = (request.GET.get("from") or request.GET.get("from_date") or "").strip()
    to_date_raw = (request.GET.get("to") or request.GET.get("to_date") or "").strip()
    invoice = (request.GET.get("invoice") or "").strip()

    date_from = _parse_iso_date(from_date_raw)
    date_to = _parse_iso_date(to_date_raw)

    all_rows, total_credit, total_debit, closing_balance = _build_party_ledger_entries(
        party=party,
        date_from=date_from,
        date_to=date_to,
        invoice_contains=invoice,
    )

    paginator = Paginator(all_rows, 20)
    page = int(request.GET.get("page", 1))
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "party": party,
        "entries": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balance": closing_balance,
        "whatsapp_url": whatsapp_message_url(party.mobile, f"Your current balance is â‚¹{closing_balance}"),
    }
    return render(request, "accounts/party_ledger.html", context)

    page = int(request.GET.get("page", 1))
    paginator = Paginator(all_rows, 20)

    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        return JsonResponse({"html": "", "has_next": False})

    html = render_to_string("accounts/ledger_entries.html", {
        "entries": page_obj.object_list
    })

    return JsonResponse({"html": html, "has_next": page_obj.has_next()})


# ---------------------------------------------------
# PDF Export – Busy Format
# ---------------------------------------------------
@login_required
def party_ledger_pdf(request, party_id):

    party = get_object_or_404(Party, id=party_id, owner=request.user)

    date_from = _parse_iso_date(request.GET.get("from"))
    date_to = _parse_iso_date(request.GET.get("to"))
    invoice = (request.GET.get("invoice") or "").strip()

    rows_desc, total_credit, total_debit, closing_balance = _build_party_ledger_entries(
        party=party,
        date_from=date_from,
        date_to=date_to,
        invoice_contains=invoice,
    )
    entries = list(reversed(rows_desc))

    context = {
        "party": party,
        "entries": entries,
        "total_credit": total_credit,
        "total_debit": total_debit,
        "balance": closing_balance,
        "generated_on": timezone.now(),
        "date_from": date_from,
        "date_to": date_to,
    }

    pdf_bytes = render_to_pdf_bytes("accounts/party_ledger_pdf.html", context, request=request)

    if pdf_bytes:
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        inline = str(request.GET.get("inline") or "").strip().lower() in {"1", "true", "yes", "on"}
        disposition = "inline" if inline else "attachment"
        resp["Content-Disposition"] = f'{disposition}; filename="ledger_{party.id}.pdf"'
        return resp

    # fallback if pdf generation fails
    return render(request, "accounts/party_ledger_pdf.html", context)

@login_required
def staff_dashboard(request):
    return render(request, "accounts/staff_dashboard.html")


# ---------------------------------------------------
# Collector Dashboard
# ---------------------------------------------------
@login_required
def collector_dashboard(request):
    agent = getattr(request.user, "field_agent_profile", None)
    if not agent or not agent.is_active:
        messages.error(request, "Collector access required.")
        return redirect("accounts:role_dashboard")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "visit_update":
            visit_id = request.POST.get("visit_id")
            status = request.POST.get("status")
            collected_amount = request.POST.get("collected_amount")
            payment_mode = request.POST.get("payment_mode")
            notes = request.POST.get("visit_notes")

            visit = get_object_or_404(CollectorVisit, id=visit_id, agent=agent)
            try:
                collected_val = Decimal(str(collected_amount or "0"))
            except Exception:
                collected_val = Decimal("0")

            visit.status = status or visit.status
            visit.collected_amount = collected_val
            visit.payment_mode = payment_mode or visit.payment_mode
            visit.notes = notes or visit.notes
            visit.marked_at = timezone.now()
            visit.save(update_fields=["status", "collected_amount", "payment_mode", "notes", "marked_at"])

            messages.success(request, "Visit updated successfully.")
            return redirect("accounts:collector_dashboard")

        if action != "create_order":
            messages.error(request, "Invalid action.")
            return redirect("accounts:collector_dashboard")

        party_id = request.POST.get("party_id")
        notes = request.POST.get("notes")
        products = request.POST.getlist("product_id[]")
        raw_names = request.POST.getlist("raw_name[]")
        qtys = request.POST.getlist("qty[]")
        prices = request.POST.getlist("price[]")

        if not party_id:
            messages.error(request, "Please select a party.")
            return redirect("accounts:collector_dashboard")

        party = agent.assigned_parties.filter(id=party_id).first()
        if not party:
            messages.error(request, "Party not assigned to you.")
            return redirect("accounts:collector_dashboard")

        from commerce.models import Order, OrderItem, Product

        with transaction.atomic():
            order = Order.objects.create(
                owner=agent.owner,
                party=party,
                order_type="SALE",
                status="pending",
                notes=notes or f"Agent order by {agent.user.get_full_name() or agent.user.email}",
                order_source="Agent",
                assigned_to=agent.user,
                agent=agent,
                placed_by="user",
                discount_type=(request.POST.get("discount_type") or "none").lower(),
                discount_value=Decimal(str(request.POST.get("discount_value") or "0")),
                tax_percent=Decimal(str(request.POST.get("tax_percent") or "0")),
            )

            valid_items = 0
            for product_id, raw_name, qty, price in zip(products, raw_names, qtys, prices):
                try:
                    qty_val = int(qty or 0)
                    price_val = Decimal(str(price or "0"))
                except Exception:
                    continue

                if qty_val <= 0 or price_val <= 0:
                    continue

                product = None
                if product_id:
                    product = Product.objects.filter(id=product_id).first()

                raw_label = raw_name or (product.name if product else "Agent Item")
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    qty=qty_val,
                    price=price_val,
                    raw_name=raw_label,
                )
                valid_items += 1

            if valid_items == 0:
                messages.error(request, "Please add at least one valid item.")
                return redirect("accounts:collector_dashboard")

            # Recompute totals after items creation
            order.compute_totals()
            order.save(update_fields=["discount_amount", "tax_amount"])

        # Auto send WhatsApp confirmation (best effort)
        settings_obj = CompanySettings.objects.first()
        if settings_obj and settings_obj.enable_auto_whatsapp and party.whatsapp_number:
            try:
                message = (
                    f"Order #{order.id} received. Total ₹{order.total_amount()}. "
                    f"Agent: {agent.user.get_full_name() or agent.user.email}."
                )
                send_whatsapp_message(party.whatsapp_number.lstrip("+"), message)
            except Exception:
                OfflineMessage.objects.create(
                    party=party,
                    recipient_name=party.name,
                    recipient_mobile=party.whatsapp_number,
                    message=message,
                    channel="whatsapp",
                    status="pending"
                )

        # Email + SMS (queue) best effort
        if party.email:
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f"Order #{order.id} Confirmation",
                    message=f"Order #{order.id} received. Total ₹{order.total_amount()}.",
                    from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, "DEFAULT_FROM_EMAIL") else None,
                    recipient_list=[party.email],
                    fail_silently=True
                )
            except Exception:
                pass

        if party.mobile:
            OfflineMessage.objects.create(
                party=party,
                recipient_name=party.name,
                recipient_mobile=party.mobile,
                message=f"Order #{order.id} received. Total ₹{order.total_amount()}.",
                channel="sms",
                status="pending"
            )

        messages.success(request, f"Order #{order.id} created. Total ₹{order.total_amount()}.")
        return redirect("accounts:collector_dashboard")

    today = timezone.now().date()
    visits_today = CollectorVisit.objects.filter(
        agent=agent,
        visit_date=today
    ).select_related("party").order_by("party__name")

    # Auto-generate visit plan if none exists for today
    if not visits_today.exists():
        for party in agent.assigned_parties.all():
            summary = get_party_summary(party)
            expected = summary.get("balance") if summary else 0
            if expected and expected > 0:
                CollectorVisit.objects.get_or_create(
                    agent=agent,
                    party=party,
                    visit_date=today,
                    defaults={
                        "expected_amount": expected,
                        "status": "planned"
                    }
                )

        visits_today = CollectorVisit.objects.filter(
            agent=agent,
            visit_date=today
        ).select_related("party").order_by("party__name")

    total_expected = visits_today.aggregate(
        total=Sum("expected_amount")
    )["total"] or Decimal("0.00")

    total_collected = visits_today.aggregate(
        total=Sum("collected_amount")
    )["total"] or Decimal("0.00")

    from commerce.models import Product, Order
    products = Product.objects.filter(owner=agent.owner).order_by("name")
    recent_agent_orders = Order.objects.filter(agent=agent).select_related("party").order_by("-created_at")[:10]

    visit_counts = {
        "planned": visits_today.filter(status="planned").count(),
        "visited": visits_today.filter(status="visited").count(),
        "partial": visits_today.filter(status="partial").count(),
        "not_available": visits_today.filter(status="not_available").count(),
        "cancelled": visits_today.filter(status="cancelled").count(),
    }

    context = {
        "agent": agent,
        "visits_today": visits_today,
        "total_expected": total_expected,
        "total_collected": total_collected,
        "today": today,
        "products": products,
        "recent_agent_orders": recent_agent_orders,
        "visit_counts": visit_counts,
    }

    return render(request, "accounts/collector_dashboard.html", context)


# ---------------------------------------------------
# Party Dashboard
# ---------------------------------------------------
@login_required
def party_dashboard(request):
    user = request.user

    mobile = None
    if user.mobile:
        mobile = user.mobile
    else:
        profile = KhataProfile.objects.filter(user=user).first()
        mobile = profile.mobile if profile else None

    party = None
    if mobile:
        party = Party.objects.filter(mobile=mobile).defer(*PARTY_SMART_KHATA_DEFER_FIELDS).first()
        if not party:
            party = (
                Party.objects.filter(whatsapp_number=mobile)
                .defer(*PARTY_SMART_KHATA_DEFER_FIELDS)
                .first()
            )

    summary = None
    invoices = []
    payments = []

    if party:
        summary = get_party_summary(party)
        invoices = Invoice.objects.filter(order__party=party).order_by("-created_at")[:10]
        payments = Payment.objects.filter(invoice__order__party=party).order_by("-created_at")[:10]

    context = {
        "party": party,
        "summary": summary,
        "invoices": invoices,
        "payments": payments,
    }

    return render(request, "accounts/party_dashboard.html", context)


# ---------------------------------------------------
# Customer Dashboard (Billing + E-commerce + B2B/B2C)
# ---------------------------------------------------
@login_required
def customer_dashboard(request):
    user = request.user
    active_tab = (request.GET.get("tab") or "overview").strip().lower()
    if active_tab not in {"overview", "ecommerce", "billing", "access"}:
        active_tab = "overview"

    # --- Billing side (Party/Invoices/Payments) ---
    mobile = None
    try:
        mobile = user.mobile or None
    except Exception:
        mobile = None
    if not mobile:
        try:
            profile = KhataProfile.objects.filter(user=user).first()
            mobile = (profile.mobile if profile else None) or None
        except Exception:
            mobile = None

    party = None
    if mobile:
        party = Party.objects.filter(mobile=mobile).defer(*PARTY_SMART_KHATA_DEFER_FIELDS).first()
        if not party:
            party = Party.objects.filter(whatsapp_number=mobile).defer(*PARTY_SMART_KHATA_DEFER_FIELDS).first()

    billing_summary = None
    invoices = []
    payments = []
    if party:
        billing_summary = get_party_summary(party)
        invoices = Invoice.objects.filter(order__party=party).order_by("-created_at")[:10]
        payments = Payment.objects.filter(invoice__order__party=party).order_by("-created_at")[:10]

    # --- E-commerce side (store orders across vendors) ---
    store_orders = []
    try:
        from storefront.models import StoreOrder

        store_orders = list(
            StoreOrder.objects.select_related("vendor")
            .filter(customer=user)
            .order_by("-created_at")[:20]
        )
    except Exception:
        store_orders = []

    store_order_cards = []
    for o in store_orders:
        try:
            track_url = reverse("store-track", kwargs={"subdomain": o.vendor.subdomain, "token": str(o.public_token)})
        except Exception:
            track_url = ""
        try:
            view_url = reverse("store-me-order-view", kwargs={"subdomain": o.vendor.subdomain, "order_id": int(o.id)})
        except Exception:
            view_url = track_url
        store_order_cards.append(
            {
                "order": o,
                "vendor": getattr(o, "vendor", None),
                "track_url": track_url,
                "view_url": view_url,
            }
        )

    # --- B2B memberships ---
    company_memberships = []
    try:
        from vendors.models import VendorCustomerCompanyMember

        company_memberships = list(
            VendorCustomerCompanyMember.objects.select_related("company", "company__vendor")
            .filter(user=user, is_active=True, company__is_active=True)
            .order_by("-created_at")[:20]
        )
    except Exception:
        company_memberships = []

    is_b2b = bool(company_memberships)

    context = {
        "active_tab": active_tab,
        "party": party,
        "billing_summary": billing_summary,
        "invoices": invoices,
        "payments": payments,
        "store_order_cards": store_order_cards,
        "company_memberships": company_memberships,
        "is_b2b": is_b2b,
    }
    return render(request, "accounts/customer_dashboard.html", context)

# ----------------- EDIT PROFILE -----------------
@login_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    can_edit_billing = can_manage_billing_hierarchy(request.user)
    can_manage_users = can_manage_linked_users(request.user)

    if not profile.plan:
        basic_plan = Plan.objects.filter(name__iexact="Basic").first()
        if basic_plan:
            profile.plan = basic_plan
            profile.save()

    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
            can_edit_billing=can_edit_billing,
        )
        if form.is_valid():
            selected_plan = form.cleaned_data.get("plan")
            user = request.user
            user.email = form.cleaned_data.get("email", user.email)
            user.first_name = form.cleaned_data.get("full_name", user.first_name)
            if can_edit_billing:
                user.billing_access_level = (form.cleaned_data.get("billing_access_level") or "").strip()
                user.billing_role_type = (form.cleaned_data.get("billing_role_type") or "").strip()
                user.billing_child_role = (form.cleaned_data.get("billing_child_role") or "").strip()
                try:
                    from billing.hierarchy import apply_billing_defaults_to_user

                    apply_billing_defaults_to_user(user, overwrite=False)
                except Exception:
                    pass

            update_fields = ["email", "first_name"]
            if can_edit_billing:
                update_fields.extend(["billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])
            user.save(update_fields=update_fields)
            form.save()

            if selected_plan and selected_plan.name.lower() != "basic":
                has_active = Subscription.objects.filter(
                    user=request.user, plan=selected_plan, status="active"
                ).exists()
                if not has_active:
                    messages.info(request, f"Redirecting to payment for {selected_plan.name} plan...")
                    return redirect(f"/billing/checkout/?plan_id={selected_plan.id}")

            messages.success(request, "🎉 Profile updated successfully!")
            return redirect("accounts:edit_profile")
        else:
            messages.error(request, "⚠️ Please correct the errors below.")
    else:
        form = UserProfileForm(
            instance=profile,
            user=request.user,
            can_edit_billing=can_edit_billing,
        )

    admin_profile = UserProfile.objects.filter(user__is_superuser=True).first()
    subscription = get_active_subscription(request.user)
    locked_count = get_locked_feature_count(request.user)
    usage_summary = get_usage_summary(request.user)

    try:
        from billing.hierarchy import billing_hierarchy_config, get_child_label, get_role_label

        billing_cfg = billing_hierarchy_config()
        billing_role_summary = {
            "access_level": getattr(request.user, "billing_access_level", "") or "",
            "role_type": getattr(request.user, "billing_role_type", "") or "",
            "child_role": getattr(request.user, "billing_child_role", "") or "",
            "role_label": get_role_label(getattr(request.user, "billing_role_type", "") or ""),
            "child_label": get_child_label(
                getattr(request.user, "billing_role_type", "") or "",
                getattr(request.user, "billing_child_role", "") or "",
            ),
        }
        billing_hierarchy_json = json.dumps(billing_cfg)
    except Exception:
        billing_role_summary = {"access_level": "", "role_type": "", "child_role": "", "role_label": "", "child_label": ""}
        billing_hierarchy_json = "{}"
    context = {
        "form": form,
        "profile": profile,
        "admin_logo": admin_profile.profile_picture.url if admin_profile and admin_profile.profile_picture else None,
        "admin_name": admin_profile.business_name if admin_profile else "",
        "admin_address": admin_profile.address if admin_profile else "",
        "admin_gst": admin_profile.gst_number if admin_profile else "",
        "admin_contact": admin_profile.mobile if admin_profile else "",
        "plan_name": profile.plan.name if profile.plan else "Basic",
        "subscription": subscription,
        "locked_features_count": locked_count,
        "usage_summary": usage_summary,
        "can_edit_billing": can_edit_billing,
        "can_manage_users": can_manage_users,
        "billing_role": billing_role_summary,
        "billing_hierarchy_json": billing_hierarchy_json,
    }

    return render(request, "accounts/edit_profile.html", context)

# ----------------- BILLING HIERARCHY API -----------------
@login_required
@require_http_methods(["GET", "POST"])
def api_billing_hierarchy(request):
    """
    Frontend helper endpoint for Billing Model Hierarchy (profile UI).
    """
    try:
        from billing.hierarchy import apply_billing_defaults_to_user, billing_hierarchy_config
    except Exception:
        apply_billing_defaults_to_user = None
        billing_hierarchy_config = None

    user = request.user
    can_edit = can_manage_billing_hierarchy(user)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "can_edit": can_edit,
                "hierarchy": billing_hierarchy_config() if billing_hierarchy_config else {},
                "current": {
                    "billing_access_level": getattr(user, "billing_access_level", "") or "",
                    "billing_role_type": getattr(user, "billing_role_type", "") or "",
                    "billing_child_role": getattr(user, "billing_child_role", "") or "",
                },
            }
        )

    if not can_edit:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads((request.body or b"").decode("utf-8"))
    except Exception:
        payload = {}

    user.billing_access_level = str(payload.get("billing_access_level") or "").strip()
    user.billing_role_type = str(payload.get("billing_role_type") or "").strip()
    user.billing_child_role = str(payload.get("billing_child_role") or "").strip()

    if apply_billing_defaults_to_user:
        try:
            apply_billing_defaults_to_user(user, overwrite=False)
        except Exception:
            pass

    user.save(
        update_fields=[
            "billing_access_level",
            "billing_role_type",
            "billing_child_role",
            "permissions_json",
        ]
    )

    return JsonResponse(
        {
            "ok": True,
            "current": {
                "billing_access_level": user.billing_access_level or "",
                "billing_role_type": user.billing_role_type or "",
                "billing_child_role": user.billing_child_role or "",
            },
        }
    )

# ----------------- AGENT / DISTRIBUTOR SIGNUP -----------------
def agent_signup_view(request):
    """
    Public registration endpoint for distributor/agent onboarding.

    - Creates a normal Django user but sets SaaS role = 'agent'
    - Optionally links to a referrer via referral_code
    - Uses the same OTP verification flow as normal signup

    Supports:
    - HTML form (GET/POST)
    - AJAX (POST with X-Requested-With: XMLHttpRequest) -> JSON response
    """

    is_ajax = (request.headers.get("x-requested-with") or "").lower() == "xmlhttprequest"

    # Preserve desired post-auth redirect (optional)
    try:
        next_q = str(request.GET.get("next") or "").strip()
        if next_q.startswith("/"):
            request.session["post_auth_redirect"] = next_q
    except Exception:
        pass

    if request.method == "POST" and not getattr(settings, "DESKTOP_MODE", False):
        try:
            max_users = int(getattr(settings, "MAX_TEST_USERS", 10))
        except Exception:
            max_users = 10
        if User.objects.filter(is_staff=False, is_superuser=False).count() >= max_users:
            if is_ajax:
                return JsonResponse({"ok": False, "message": f"Signup disabled: testing limit reached ({max_users} users)."}, status=403)
            messages.error(request, f"Signup disabled: testing limit reached ({max_users} users).")
            return redirect("accounts:login")

    if request.method == "POST":
        form = AgentSignupForm(request.POST)
        if form.is_valid():
            try:
                desktop_bypass = bool(getattr(settings, "DESKTOP_MODE", False) and getattr(settings, "OTP_BYPASS", False))
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.role = "agent"
                    user.is_active = desktop_bypass
                    user.is_otp_verified = desktop_bypass

                    ref_code = (form.cleaned_data.get("referrer_code") or "").strip()
                    if ref_code:
                        referrer = User.objects.filter(referral_code__iexact=ref_code).first()
                        if referrer:
                            user.parent = referrer
                            user.referred_by = referrer

                    user.save()

                    otp = None
                    if not desktop_bypass:
                        otp = OTP.create_for(
                            user=user,
                            purpose="signup",
                            email=user.email,
                            mobile=form.cleaned_data.get("mobile"),
                        )

                # Ensure khata profile exists (used across the app)
                try:
                    profile = KhataProfile.objects.get(user=user)
                except KhataProfile.DoesNotExist:
                    profile = KhataProfile.objects.create(
                        user=user,
                        created_from="signup",
                        plan=None,
                        mobile=form.cleaned_data.get("mobile"),
                        full_name=user.get_full_name() or user.username,
                    )

                # Give a free plan so feature gating works consistently
                try:
                    ensure_free_plan(user)
                except Exception:
                    pass

                if desktop_bypass:
                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    login(request, user)
                    if is_ajax:
                        return JsonResponse({"ok": True, "message": "Account created successfully.", "redirect_url": "/accounts/dashboard/"})
                    messages.success(request, "Account created successfully.")
                    return redirect("/accounts/dashboard/")

                if otp is not None:
                    send_otp_code(to_email=user.email, to_mobile=profile.mobile, code=otp.code)

                request.session["otp_user_id"] = user.id
                request.session["otp_purpose"] = "signup"

                if is_ajax:
                    return JsonResponse(
                        {
                            "ok": True,
                            "message": "OTP sent. Please verify your account.",
                            "redirect_url": reverse("accounts:verify_otp"),
                        }
                    )

                messages.success(request, "OTP sent. Please verify your account.")
                return redirect("accounts:verify_otp")

            except Exception as e:
                if is_ajax:
                    return JsonResponse({"ok": False, "message": f"Signup failed: {e}"}, status=400)
                messages.error(request, f"Signup failed: {e}")
        else:
            if is_ajax:
                return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)

    else:
        form = AgentSignupForm()

    return render(request, "accounts/agent_signup.html", {"form": form})

# ----------------- SIGNUP -----------------
def signup_view(request):
    # Limit system to a small number of non-staff users for testing.
    # Admin/staff can still create users via admin if needed.
    # NOTE: Desktop EXE ships with a bundled SQLite that may contain demo/sample users.
    # Enforcing this limit in DESKTOP_MODE can unintentionally block real signups.
    if request.method == "POST" and not getattr(settings, "DESKTOP_MODE", False):
        try:
            max_users = int(getattr(settings, "MAX_TEST_USERS", 10))
        except Exception:
            max_users = 10
        if User.objects.filter(is_staff=False, is_superuser=False).count() >= max_users:
            messages.error(request, f"Signup disabled: testing limit reached ({max_users} users).")
            return redirect("accounts:login")

    # Preserve desired post-auth redirect from landing CTAs (e.g. /billing/checkout/?plan_id=...).
    try:
        next_q = str(request.GET.get("next") or "").strip()
        if next_q.startswith("/"):
            request.session["post_auth_redirect"] = next_q
    except Exception:
        pass

    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            try:
                desktop_bypass = bool(getattr(settings, "DESKTOP_MODE", False) and getattr(settings, "OTP_BYPASS", False))
                with transaction.atomic():
                    user = form.save(commit=False)
                    # Desktop OTP-bypass: avoid multi-step OTP/session flow in embedded WebViews.
                    user.is_active = desktop_bypass
                    user.is_otp_verified = desktop_bypass
                    user.save()

                    otp = None
                    if not desktop_bypass:
                        otp = OTP.create_for(
                            user=user,
                            purpose="signup",
                            email=user.email,
                            mobile=form.cleaned_data.get("mobile"),
                        )

                # Create khataapp profile OUTSIDE transaction to avoid FK constraint issues
                try:
                    profile = KhataProfile.objects.get(user=user)
                except KhataProfile.DoesNotExist:
                    profile = KhataProfile.objects.create(
                        user=user,
                        created_from="signup",
                        plan=None,
                        mobile=form.cleaned_data.get("mobile"),
                        full_name=user.get_full_name() or user.username
                    )
                # Auto-assign default plan (if configured) else Free plan + subscription.
                # Note: subscriptions are the source of truth for `get_effective_plan()`.
                try:
                    from khataapp.models import CompanySettings as KhataCompanySettings
                    from billing.services import upgrade_subscription

                    cs = KhataCompanySettings.objects.select_related("default_plan").order_by("id").first()
                    default_plan = getattr(cs, "default_plan", None)
                    if default_plan and getattr(default_plan, "active", True):
                        upgrade_subscription(user, default_plan)
                    else:
                        ensure_free_plan(user)
                except Exception:
                    try:
                        ensure_free_plan(user)
                    except Exception:
                        pass

                if desktop_bypass:
                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    login(request, user)
                    messages.success(request, "Account created successfully.")
                    next_url = request.session.pop("post_auth_redirect", None)
                    if isinstance(next_url, str) and next_url.startswith("/"):
                        return redirect(next_url)
                    return role_based_redirect(user)

                # OTP delivery (SMS + Email + WhatsApp) outside transaction
                if otp is not None:
                    send_otp_code(to_email=user.email, to_mobile=profile.mobile, code=otp.code)

                request.session["otp_user_id"] = user.id
                request.session["otp_purpose"] = "signup"

                messages.success(request, "OTP sent. Please verify your account.")
                return redirect("accounts:verify_otp")

            except Exception as e:
                messages.error(request, f"Signup failed: {e}")
                return redirect("accounts:signup")

    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})

# ----------------- LOGIN -----------------
@xframe_options_exempt
def login_view(request):
    # Preserve desired post-auth redirect from landing CTAs (e.g. /billing/checkout/?plan_id=...).
    try:
        next_q = str(request.GET.get("next") or "").strip()
        if next_q.startswith("/"):
            request.session["post_auth_redirect"] = next_q
    except Exception:
        pass

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            role = str(form.cleaned_data.get("role") or "user").strip().lower()
            identifier = form.cleaned_data["identifier"]
            password = form.cleaned_data["password"]
            use_otp = form.cleaned_data.get("use_otp", True)

            # If the login was triggered by a storefront page, treat "Customer" selection as
            # a normal app login (store customer), not the Business Portal customer account.
            # This keeps the UX simple for e-commerce flows: /store/<vendor>/me/orders/ -> login -> return.
            try:
                next_target = str(request.session.get("post_auth_redirect") or next_q or "").strip()
            except Exception:
                next_target = ""
            if role in {"customer", "supplier"} and next_target.startswith("/store/"):
                role = "user"

            # ----------------- PORTAL LOGIN (Customer/Supplier) -----------------
            if role in {"customer", "supplier"}:
                # Portal availability (admin settings)
                try:
                    from portal.services import customer_portal_enabled, portal_enabled, supplier_portal_enabled

                    if not portal_enabled():
                        messages.error(request, "Portal login is currently disabled by admin settings.")
                        return render(request, "accounts/login.html", {"form": form})
                    if role == "customer" and not customer_portal_enabled():
                        messages.error(request, "Customer portal is currently disabled by admin settings.")
                        return render(request, "accounts/login.html", {"form": form})
                    if role == "supplier" and not supplier_portal_enabled():
                        messages.error(request, "Supplier portal is currently disabled by admin settings.")
                        return render(request, "accounts/login.html", {"form": form})
                except Exception:
                    # Never block ERP login because of portal settings read errors.
                    pass

                # Portal accounts use username + password (no OTP).
                if not password:
                    messages.error(request, "Password is required for portal login.")
                    return render(request, "accounts/login.html", {"form": form})
                try:
                    from portal.models import PortalUser
                except Exception:
                    messages.error(request, "Portal module unavailable.")
                    return render(request, "accounts/login.html", {"form": form})

                pu = PortalUser.objects.select_related("party", "owner").filter(username__iexact=identifier, role=role).first()
                if not pu or not pu.is_active or not pu.check_password(password):
                    messages.error(request, "Invalid portal credentials.")
                    return render(request, "accounts/login.html", {"form": form})

                try:
                    request.session.cycle_key()
                except Exception:
                    pass
                request.session["portal_user_id"] = pu.id
                request.session["portal_role"] = pu.role
                try:
                    pu.touch_login()
                except Exception:
                    pass

                messages.success(request, "Portal login successful.")
                if getattr(pu, "must_change_password", False):
                    return redirect("portal:change_password")
                if pu.role == "supplier":
                    return redirect("portal:supplier_dashboard")
                return redirect("portal:customer_dashboard")

            # Find user by mobile or email
            user = None
            mobile_for_otp = None
            
            profile = KhataProfile.objects.filter(mobile=identifier).select_related("user").first()
            if profile:
                user = profile.user
                mobile_for_otp = profile.mobile
            else:
                # Try to find user by email
                try:
                    user = User.objects.get(email__iexact=identifier)
                    # Get mobile from user's profile if exists
                    user_profile = KhataProfile.objects.filter(user=user).first()
                    mobile_for_otp = user_profile.mobile if user_profile else None
                except User.DoesNotExist:
                    # Fallback: allow login by username or direct user.mobile for backward compatibility.
                    user = User.objects.filter(username__iexact=identifier).first()
                    if not user:
                        # If the identifier looks like digits, try matching the custom user mobile field.
                        digits = "".join([c for c in (identifier or "") if c.isdigit()])
                        if digits:
                            user = User.objects.filter(mobile=digits).first()
                    if user:
                        user_profile = KhataProfile.objects.filter(user=user).first()
                        mobile_for_otp = user_profile.mobile if user_profile else getattr(user, "mobile", None)
                    else:
                        messages.error(request, "User not found")
                        return render(request, "accounts/login.html", {"form": form})

            # Ensure user is not None before proceeding
            if not user:
                messages.error(request, "User not found")
                return render(request, "accounts/login.html", {"form": form})

            # Role guardrails (UI selection)
            if role == "admin" and not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
                messages.error(request, "This account does not have admin access.")
                return render(request, "accounts/login.html", {"form": form})

            # ---- OTP LOGIN ----
            if use_otp:
                # Preserve desired redirect for OTP verification step.
                try:
                    if role == "admin" and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
                        request.session["post_otp_redirect"] = "/superadmin/"
                    else:
                        request.session.pop("post_otp_redirect", None)
                except Exception:
                    pass

                # Desktop convenience: in OTP bypass mode, skip the OTP step entirely.
                # This avoids session/cookie edge cases in embedded desktop WebViews.
                if getattr(settings, "DESKTOP_MODE", False) and getattr(settings, "OTP_BYPASS", False):
                    user.is_active = True
                    user.is_otp_verified = True
                    user.save(update_fields=["is_active", "is_otp_verified"])

                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    login(request, user)
                    next_url = request.session.pop("post_auth_redirect", None)
                    if isinstance(next_url, str) and next_url.startswith("/"):
                        return redirect(next_url)
                    if role == "admin" and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
                        return redirect("/superadmin/")
                    return role_based_redirect(user)

                otp = OTP.create_for(
                    user=user,
                    purpose="login",
                    email=user.email,
                    mobile=mobile_for_otp,
                )

                send_otp_code(to_email=user.email, to_mobile=mobile_for_otp, code=otp.code)

                request.session["otp_user_id"] = user.id
                request.session["otp_purpose"] = "login"

                messages.info(request, "OTP sent. Please verify.")
                return redirect("accounts:verify_otp")

            # ---- NORMAL PASSWORD LOGIN ----
            if not password:
                messages.error(request, "Password is required when OTP login is off.")
                return render(request, "accounts/login.html", {"form": form})

            # Our custom User model uses email as USERNAME_FIELD.
            user_auth = authenticate(request, username=user.get_username(), password=password)
            if user_auth:
                login(request, user_auth)
                next_url = request.session.pop("post_auth_redirect", None)
                if isinstance(next_url, str) and next_url.startswith("/"):
                    return redirect(next_url)
                if role == "admin" and (getattr(user_auth, "is_staff", False) or getattr(user_auth, "is_superuser", False)):
                    return redirect("/superadmin/")
                return role_based_redirect(user_auth)

            # If credentials are correct but the user is inactive, ModelBackend returns None.
            # Surface a clearer error and route to OTP verification.
            if user.check_password(password) and not user.is_active:
                messages.error(request, "Verify OTP first")
                request.session["otp_user_id"] = user.id
                request.session["otp_purpose"] = "login"
                return redirect("accounts:verify_otp")

            messages.error(request, "Invalid credentials")

    else:
        initial = {}
        role_q = str(request.GET.get("role") or "").strip().lower()
        if role_q in {"user", "admin", "customer", "supplier"}:
            initial["role"] = role_q
        form = LoginForm(initial=initial or None)

    return render(request, "accounts/login.html", {"form": form})


# ----------------- OTP VERIFY -----------------
def verify_otp_view(request):

    user_id = request.session.get("otp_user_id")

    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("accounts:login")

    user = get_object_or_404(User, id=user_id)

    # ✅ TEMPORARY BYPASS (Render free deploy helper)
    if getattr(settings, "OTP_BYPASS", False):
        user.is_active = True
        user.is_otp_verified = True
        user.save(update_fields=["is_active", "is_otp_verified"])

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)

        request.session.pop("otp_user_id", None)
        request.session.pop("otp_purpose", None)

        messages.warning(request, "⚠ OTP bypass mode active (temporary).")

        next_url = request.session.pop("post_auth_redirect", None)
        if isinstance(next_url, str) and next_url.startswith("/"):
            return redirect(next_url)

        next_url = request.session.pop("post_otp_redirect", None)
        if isinstance(next_url, str) and next_url.startswith("/"):
            return redirect(next_url)
        if user.is_superuser:
            return redirect("/superadmin/")
        return redirect("/accounts/dashboard/")


    # ✅ NORMAL FLOW (PRODUCTION SAFE)
    if request.method == "POST":
        form = OTPForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data["code"]

            otp = OTP.objects.filter(
                user=user,
                verified=False,
                expires_at__gte=timezone.now()
            ).order_by("-created_at").first()

            if not otp:
                messages.error(request, "OTP expired. Please resend.")
                return redirect("accounts:verify_otp")

            if otp.code != code:
                messages.error(request, "Invalid OTP.")
                return redirect("accounts:verify_otp")

            otp.verified = True
            otp.save(update_fields=["verified"])

            user.is_active = True
            user.is_otp_verified = True
            user.save(update_fields=["is_active", "is_otp_verified"])

            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)

            request.session.pop("otp_user_id", None)
            request.session.pop("otp_purpose", None)

            messages.success(request, "Account verified successfully.")

            next_url = request.session.pop("post_auth_redirect", None)
            if isinstance(next_url, str) and next_url.startswith("/"):
                return redirect(next_url)

            next_url = request.session.pop("post_otp_redirect", None)
            if isinstance(next_url, str) and next_url.startswith("/"):
                return redirect(next_url)
            if user.is_superuser:
                return redirect("/superadmin/")
            else:
                return redirect("accounts:role_dashboard")

    else:
        form = OTPForm()

    return render(request, "accounts/verify_otp.html", {
        "form": form,
        "user": user
    })


# ----------------- LOGOUT -----------------
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


# ---------------------------------------------------
# Login via Secure Link (WhatsApp First)
# ---------------------------------------------------
def login_link_view(request, token):
    link = get_object_or_404(LoginLink, token=token, is_active=True)
    if not link.is_valid():
        messages.error(request, "Link expired or invalid. Please request a new link.")
        return redirect("accounts:login")

    user = link.user

    mobile_for_otp = None
    profile = KhataProfile.objects.filter(user=user).first()
    if profile and profile.mobile:
        mobile_for_otp = profile.mobile
    elif user.mobile:
        mobile_for_otp = user.mobile

    otp = OTP.create_for(
        user=user,
        purpose="login",
        email=user.email,
        mobile=mobile_for_otp,
    )

    send_otp_code(to_email=user.email, to_mobile=mobile_for_otp, code=otp.code)

    link.last_used_at = timezone.now()
    link.save(update_fields=["last_used_at"])

    request.session["otp_user_id"] = user.id
    request.session["otp_purpose"] = "login"

    messages.info(request, "OTP sent. Please verify to continue.")
    return redirect("accounts:verify_otp")


# ----------------- PROFILE SETTINGS (Legacy Support) -----------------
@login_required
def profile_settings(request):
    """Optional: keep for backward compatibility"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    can_edit_billing = can_manage_billing_hierarchy(request.user)

    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
            can_edit_billing=can_edit_billing,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:dashboard")
    else:
        form = UserProfileForm(
            instance=profile,
            user=request.user,
            can_edit_billing=can_edit_billing,
        )

    return render(request, "accounts/profile_settings.html", {"form": form})


# ----------------- SUBSCRIBE PLAN -----------------
@login_required
def subscribe_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.plan = plan
    profile.save()
    messages.success(request, f"Subscribed to {plan.name} plan.")
    return redirect("accounts:dashboard")

@login_required
def upgrade_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    user = request.user

    # ✅ Create unpaid invoice
    invoice = Invoice.objects.create(
        user=user,
        plan=plan,
        amount=plan.price_per_month,
        status="pending"
    )

    # Redirect to your payment gateway (Razorpay, Stripe, etc.)
    return redirect(f"/billing/pay/{invoice.id}/")

@login_required
def daily_summary_view(request):
    user = request.user

    # Always ensure user is a valid User object
    if not isinstance(user, User):
        user = User.objects.filter(username=user).first()
        if not user:
            return HttpResponse("Invalid user. Contact admin.")

    today = date.today()

    summary = DailySummary.objects.filter(user=user, date=today).first()

    if summary is None:
        transactions = Transaction.objects.filter(
            party__owner=user,
            date=today
        )

        total_debit = transactions.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or 0
        total_credit = transactions.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or 0

        balance = total_debit - total_credit

        summary = DailySummary.objects.create(
            user=user,
            date=today,
            total_credit=total_credit,
            total_debit=total_debit,
            balance=balance,
            total_transactions=transactions.count(),
        )

    return render(request, "accounts/daily_summary.html", {"summary": summary})


# -------------------------------------------------------
# SAFE UPDATE FUNCTION – WILL NEVER CRASH OR TAKE STRING
# -------------------------------------------------------

def update_daily_summary(user):

    # 1. Convert anything to User object safely
    if isinstance(user, User):
        pass
    elif isinstance(user, int):
        user = User.objects.filter(id=user).first()
    elif isinstance(user, str):
        user = User.objects.filter(username=user).first()
    else:
        return None

    if not user:
        return None

    today = timezone.now().date()

    transactions = Transaction.objects.filter(
        party__owner=user,
        date=today
    )

    total_credit = transactions.filter(txn_type='credit').aggregate(total=Sum('amount'))['total'] or 0
    total_debit = transactions.filter(txn_type='debit').aggregate(total=Sum('amount'))['total'] or 0
    balance = total_debit - total_credit

    summary, created = DailySummary.objects.get_or_create(
        user=user,
        date=today,
        defaults={
            'total_credit': total_credit,
            'total_debit': total_debit,
            'balance': balance,
            'total_transactions': transactions.count(),
        }
    )

    summary.total_credit = total_credit
    summary.total_debit = total_debit
    summary.balance = balance
    summary.total_transactions = transactions.count()
    summary.save()

    return summary

@login_required
def business_snapshot_view(request):
    selected = parse_date(request.GET.get("date") or "") or now().date()
    snapshot = build_business_snapshot(request.user, selected)
    return render(
        request,
        "accounts/business_snapshot.html",
        {"snapshot": snapshot, "selected_date": selected}
    )

@login_required
def loyalty_dashboard(request):
    _ensure_demo_loyalty_data(request.user)
    loyalty_account = LoyaltyPoints.objects.filter(user=request.user).select_related("program", "current_tier").first()
    program = LoyaltyProgram.objects.filter(is_active=True).first()
    tiers = MembershipTier.objects.filter(is_active=True).order_by("min_points_required")
    offers = [o for o in SpecialOffer.objects.filter(is_active=True) if o.is_valid_for_user(request.user)]
    transactions = []
    next_tier = None
    tier_progress = 0
    points_to_next_tier = 0

    if loyalty_account:
        transactions = loyalty_account.transactions.all()[:12]
        if loyalty_account.current_tier:
            next_tier = tiers.filter(min_points_required__gt=loyalty_account.current_tier.min_points_required).first()
        else:
            next_tier = tiers.first()

        if next_tier:
            current_floor = loyalty_account.current_tier.min_points_required if loyalty_account.current_tier else 0
            tier_span = max(next_tier.min_points_required - current_floor, 1)
            earned_in_tier = max(loyalty_account.total_points - current_floor, 0)
            tier_progress = min(int((earned_in_tier / tier_span) * 100), 100)
            points_to_next_tier = max(next_tier.min_points_required - loyalty_account.total_points, 0)
        else:
            tier_progress = 100

    return render(
        request,
        "accounts/loyalty_dashboard.html",
        {
            "loyalty_account": loyalty_account,
            "program": program,
            "tiers": tiers,
            "offers": offers,
            "transactions": transactions,
            "next_tier": next_tier,
            "tier_progress": tier_progress,
            "points_to_next_tier": points_to_next_tier,
        },
    )


def _ensure_demo_loyalty_data(user):
    """Keep the Demo Test 3 loyalty page populated for walkthroughs."""
    if not getattr(user, "is_authenticated", False):
        return

    profile = UserProfile.objects.filter(user=user).first()
    is_demo_user = (
        (user.username or "").lower() == "demotest3"
        or (user.email or "").lower().startswith("demotest3")
        or (profile and (profile.full_name or "").strip().lower() == "demo test 3")
    )
    if not is_demo_user:
        return

    program, _ = LoyaltyProgram.objects.get_or_create(
        name="Billentra Rewards",
        defaults={
            "description": "Demo rewards program for repeat customers.",
            "points_per_rupee": Decimal("1.00"),
            "points_to_rupee_ratio": Decimal("0.10"),
            "min_redeem_points": 100,
            "is_active": True,
        },
    )
    if not program.is_active:
        program.is_active = True
        program.save(update_fields=["is_active"])

    tier_specs = [
        ("bronze", "Bronze", 0, Decimal("0.00"), Decimal("1.00"), 50, 100, Decimal("0.00")),
        ("silver", "Silver", 1500, Decimal("25000.00"), Decimal("1.25"), 100, 250, Decimal("499.00")),
        ("gold", "Gold", 5000, Decimal("75000.00"), Decimal("1.50"), 250, 500, Decimal("999.00")),
        ("platinum", "Platinum", 12000, Decimal("150000.00"), Decimal("2.00"), 500, 1000, Decimal("1999.00")),
    ]
    tiers_by_name = {}
    for name, display, min_points, min_amount, multiplier, birthday, festival, price in tier_specs:
        tier, _ = MembershipTier.objects.update_or_create(
            name=name,
            defaults={
                "display_name": display,
                "description": f"{display} demo membership tier",
                "min_points_required": min_points,
                "min_transaction_amount": min_amount,
                "points_multiplier": multiplier,
                "birthday_bonus_points": birthday,
                "festival_bonus_points": festival,
                "upgrade_price": price,
                "is_active": True,
            },
        )
        tiers_by_name[name] = tier

    loyalty, created = LoyaltyPoints.objects.get_or_create(
        user=user,
        program=program,
        defaults={
            "total_points": 7250,
            "available_points": 6420,
            "used_points": 830,
            "current_tier": tiers_by_name["gold"],
            "total_earned": Decimal("98500.00"),
            "last_transaction_date": timezone.now() - timedelta(days=1),
        },
    )
    if created or loyalty.available_points < 5000:
        loyalty.total_points = 7250
        loyalty.available_points = 6420
        loyalty.used_points = 830
        loyalty.current_tier = tiers_by_name["gold"]
        loyalty.total_earned = Decimal("98500.00")
        loyalty.last_transaction_date = timezone.now() - timedelta(days=1)
        loyalty.save()

    demo_transactions = [
        ("earn", 420, Decimal("4200.00"), "POS sale reward - invoice INV-DEMO-1042", 1),
        ("bonus", 500, Decimal("0.00"), "Festival bonus credited", 3),
        ("earn", 760, Decimal("7600.00"), "Wholesale order reward", 6),
        ("redeem", -300, Decimal("0.00"), "Redeemed against purchase discount", 9),
        ("earn", 980, Decimal("9800.00"), "Repeat customer milestone", 12),
        ("bonus", 250, Decimal("0.00"), "Gold tier monthly bonus", 15),
    ]
    for tx_type, points, amount, description, days_ago in demo_transactions:
        tx, created_tx = PointsTransaction.objects.get_or_create(
            loyalty_account=loyalty,
            description=description,
            defaults={
                "transaction_type": tx_type,
                "points": points,
                "amount": amount,
            },
        )
        if created_tx:
            PointsTransaction.objects.filter(id=tx.id).update(created_at=timezone.now() - timedelta(days=days_ago))

    today = timezone.now().date()
    offer_specs = [
        ("Gold Member Cashback", "custom", "Extra cashback for Gold members on repeat purchases.", 300, Decimal("5.00"), Decimal("0.00"), tiers_by_name["gold"], 3000),
        ("Festival Scratch Bonus", "festival", "Limited-time scratch bonus for active reward users.", 750, Decimal("0.00"), Decimal("250.00"), tiers_by_name["silver"], 1500),
    ]
    for name, offer_type, description, bonus, pct, amount, min_tier, min_points in offer_specs:
        SpecialOffer.objects.update_or_create(
            name=name,
            defaults={
                "offer_type": offer_type,
                "description": description,
                "is_active": True,
                "auto_apply": True,
                "bonus_points": bonus,
                "discount_percentage": pct,
                "discount_amount": amount,
                "valid_from": today - timedelta(days=7),
                "valid_until": today + timedelta(days=30),
                "min_tier": min_tier,
                "min_points": min_points,
            },
        )

# -------------------------------------------------------
# SAFE UPDATE FUNCTION – WILL NEVER CRASH OR TAKE STRING
# -------------------------------------------------------
@login_required
def create_expense(request):
    categories = ExpenseCategory.objects.filter(created_by=request.user)

    if request.method == "POST":
        category_name = (request.POST.get("new_category") or "").strip()
        category_id = request.POST.get("category")
        expense_date = request.POST.get("expense_date")
        description = (request.POST.get("description") or "").strip()
        amount_paid = request.POST.get("amount_paid")
        vendor_name = (request.POST.get("vendor_name") or "").strip()
        invoice_number = (request.POST.get("invoice_number") or "").strip()
        payment_mode = (request.POST.get("payment_mode") or "cash").strip()
        gst_amount = request.POST.get("gst_amount") or "0"
        receipt_file = request.FILES.get("receipt_file")

        def _expense_context():
            return {
                "categories": categories,
                "today": now().date(),
                "payment_modes": Expense.PaymentMode.choices,
            }

        if category_name:
            category = ExpenseCategory.objects.create(
                name=category_name,
                created_by=request.user
            )
        else:
            if not category_id:
                messages.error(request, "Please select a category or create a new one.")
                return render(request, "accounts/expense_create.html", _expense_context())
            category = ExpenseCategory.objects.filter(id=category_id, created_by=request.user).first()
            if not category:
                messages.error(request, "Invalid category selected.")
                return render(request, "accounts/expense_create.html", _expense_context())

        if receipt_file and receipt_file.size > 10 * 1024 * 1024:
            messages.error(request, "Invoice/receipt file 10 MB se chhota hona chahiye.")
            return render(request, "accounts/expense_create.html", _expense_context())

        ocr_status = ""
        ocr_text = ""
        ocr_payload = {}
        if receipt_file:
            ocr_status = "uploaded"
            try:
                current_pos = receipt_file.tell()
                from ai_ocr.invoice_reader import read_invoice_from_upload

                result = read_invoice_from_upload(receipt_file)
                receipt_file.seek(current_pos)
                if result.ok and result.parsed:
                    ocr_status = "parsed"
                    ocr_text = result.ocr.text or ""
                    ocr_payload = {
                        "supplier_name": result.parsed.supplier_name,
                        "invoice_no": result.parsed.invoice_no,
                        "invoice_date": result.parsed.invoice_date,
                        "totals": result.parsed.totals,
                    }
                    vendor_name = vendor_name or result.parsed.supplier_name
                    invoice_number = invoice_number or result.parsed.invoice_no
                    total = result.parsed.totals.get("grand_total") or result.parsed.totals.get("total")
                    if total and not amount_paid:
                        amount_paid = str(total)
                else:
                    ocr_status = "uploaded"
                    ocr_text = getattr(result.ocr, "text", "") or ""
            except Exception as exc:
                try:
                    receipt_file.seek(0)
                except Exception:
                    pass
                ocr_status = "ocr_failed"
                ocr_payload = {"error": str(exc)[:240]}

        expense = Expense.objects.create(
            expense_number=f"EXP-{uuid.uuid4().hex[:6].upper()}",
            expense_date=expense_date,
            category=category,
            description=description,
            amount_paid=amount_paid,
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            payment_mode=payment_mode if payment_mode in dict(Expense.PaymentMode.choices) else Expense.PaymentMode.CASH,
            gst_amount=gst_amount,
            receipt_file=receipt_file,
            ocr_status=ocr_status,
            ocr_text=ocr_text,
            ocr_payload=ocr_payload,
            created_by=request.user
        )

        messages.success(request, f"Expense {expense.expense_number} saved successfully.")
        return redirect("accounts:expense_list")

    return render(request, "accounts/expense_create.html", {
        "categories": categories,
        "today": now().date(),
        "payment_modes": Expense.PaymentMode.choices,
    })

@login_required
def expense_list(request):
    expenses = Expense.objects.filter(created_by=request.user).order_by("-expense_date")
    return render(request, "accounts/expense_list.html", {
        "expenses": expenses
    })

@login_required
@require_POST
def redeem_points(request):
    """
    Redeem loyalty points securely.
    Supports web, mobile app, API clients.
    """

    # -------------------------
    # 1️⃣ Parse JSON safely
    # -------------------------
    try:
        payload = json.loads(request.body.decode("utf-8"))
        points = int(payload.get("points", 0))
        description = payload.get(
            "description",
            "Points redeemed by user"
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON payload"},
            status=400
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Points must be a valid number"},
            status=400
        )

    # -------------------------
    # 2️⃣ Validate points
    # -------------------------
    if points <= 0:
        return JsonResponse(
            {"error": "Points must be greater than zero"},
            status=400
        )

    # -------------------------
    # 3️⃣ Atomic transaction (SAFE)
    # -------------------------
    try:
        with transaction.atomic():

            # User profile
            profile = UserProfile.objects.select_for_update().get(
                user=request.user
            )

            # Loyalty account
            loyalty = LoyaltyPoints.objects.select_for_update().get(
                user=request.user
            )

            if loyalty.available_points < points:
                return JsonResponse(
                    {"error": "Insufficient reward points"},
                    status=400
                )

            # Redeem using model method (BEST PRACTICE)
            loyalty.redeem_points(
                points=points,
                description=description
            )

            # Optional sync with profile (if you use both)
            profile.reward_points = loyalty.available_points
            profile.save(update_fields=["reward_points"])

    except UserProfile.DoesNotExist:
        return JsonResponse(
            {"error": "User profile not found"},
            status=404
        )

    except LoyaltyPoints.DoesNotExist:
        return JsonResponse(
            {"error": "Loyalty account not found"},
            status=404
        )

    except Exception as e:
        return JsonResponse(
            {"error": "Something went wrong", "details": str(e)},
            status=500
        )

    # -------------------------
    # 4️⃣ Success response
    # -------------------------
    return JsonResponse({
        "success": True,
        "message": f"{points} points redeemed successfully",
        "remaining_points": loyalty.available_points,
    })
