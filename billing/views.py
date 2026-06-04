from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count
import json
import hmac
import hashlib
from decimal import Decimal
import requests
import secrets

# ✅ Import all models properly
from .models import (
    Plan, Subscription, BillingInvoice, PaymentGateway, Payment,
    Order, OrderItem, Warehouse, Stock, ChatMessage, ChatThread,
    Notification, PartyPortal
)
from .forms import CommerceForm, LinkedBillingUserForm   # if used later

from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from billing.services import (
    sync_feature_registry,
    get_active_subscription,
    upgrade_subscription,
    get_effective_plan,
)
from billing.models import FeatureRegistry, PlanFeature, SubscriptionHistory
from django.views.decorators.http import require_POST
from khataapp.models import UserProfile as KhataProfile
from billing.models import UserFeatureOverride
from billing.services import ensure_user_feature_overrides

User = get_user_model()


def _can_manage_linked_users(user) -> bool:
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


def _linked_users_qs(owner):
    return User.objects.filter(parent=owner).order_by("-date_joined", "-id")


def _safe_reverse(name: str, args=None, kwargs=None, default: str = "") -> str:
    try:
        return reverse(name, args=args or [], kwargs=kwargs or {})
    except Exception:
        return default or ""


def _build_abs(request, path: str) -> str:
    try:
        return request.build_absolute_uri(path)
    except Exception:
        return path or ""


def _portal_links_for_user(member) -> dict:
    """
    Returns dict of portal/dashboard links based on billing_role_type.
    All are relative URLs (reverse-resolved where possible).
    """
    role_type = (getattr(member, "billing_role_type", "") or "").strip()
    links = {"after_login": []}

    # Default dashboard
    links["after_login"].append({"label": "Main Dashboard", "url": _safe_reverse("accounts:dashboard", default="/accounts/dashboard/")})

    if role_type == "customer":
        links["after_login"].extend(
            [
                {"label": "Customer Portal Dashboard", "url": _safe_reverse("portal:customer_dashboard", default="/portal/customer/dashboard/")},
                {"label": "Customer E-commerce", "url": _safe_reverse("portal:customer_ecommerce_dashboard", default="/portal/customer/ecommerce/")},
                {"label": "Customer Billing", "url": _safe_reverse("portal:customer_billing_dashboard", default="/portal/customer/billing/")},
            ]
        )
    elif role_type == "supplier":
        links["after_login"].extend(
            [
                {"label": "Supplier Portal Dashboard", "url": _safe_reverse("portal:supplier_dashboard", default="/portal/supplier/dashboard/")},
                {"label": "Supplier Purchases", "url": _safe_reverse("portal:supplier_purchases_dashboard", default="/portal/supplier/purchases/")},
                {"label": "Supplier Billing", "url": _safe_reverse("portal:supplier_billing_dashboard", default="/portal/supplier/billing/")},
            ]
        )
    elif role_type == "vendor":
        # If user is linked to a Vendor model that has a subdomain, link to storefront vendor dashboard UI.
        try:
            seller = getattr(member, "seller", None)
            sub = getattr(seller, "subdomain", None) if seller else None
            if sub:
                links["after_login"].append(
                    {"label": "Vendor Dashboard", "url": _safe_reverse("vendor-dashboard-ui", args=[sub])}
                )
        except Exception:
            pass
        links["after_login"].append({"label": "Commerce Dashboard", "url": _safe_reverse("billing:commerce_dashboard", default="/billing/commerce-dashboard/")})
    elif role_type == "field_agent":
        links["after_login"].append({"label": "Field Agents (Manage)", "url": _safe_reverse("khataapp:field_agent_list", default="/khataapp/agents/manage/")})
    elif role_type == "sub_user":
        links["after_login"].append({"label": "Profile / Settings", "url": _safe_reverse("accounts:edit_profile", default="/accounts/dashboard/edit/")})

    return links


def _allowed_links_for_user(request, member) -> dict:
    """
    Like `_portal_links_for_user` but filters to only what the user effectively has access to
    (based on feature gates + permission toggles).
    """
    def can(key: str) -> bool:
        try:
            return bool(member.has_permission(key))
        except Exception:
            return False

    role_type = (getattr(member, "billing_role_type", "") or "").strip()
    links = {"after_login": []}

    # Role router (best default)
    links["after_login"].append(
        {
            "label": "Role Dashboard",
            "url": _safe_reverse("accounts:role_dashboard", default="/accounts/role-dashboard/"),
        }
    )

    # Billing dashboard access
    if can("billing.user.manage_billing") or can("billing.user.view_reports") or getattr(member, "is_staff", False):
        links["after_login"].append(
            {"label": "Billing Dashboard", "url": _safe_reverse("billing:dashboard", default="/billing/dashboard/")}
        )

    if role_type == "customer":
        if can("feature:portal.customer"):
            links["after_login"].append(
                {"label": "Customer Portal Dashboard", "url": _safe_reverse("portal:customer_dashboard", default="/portal/customer/dashboard/")}
            )
            if can("portal.place_orders"):
                links["after_login"].append(
                    {"label": "Customer E-commerce", "url": _safe_reverse("portal:customer_ecommerce_dashboard", default="/portal/customer/ecommerce/")}
                )
            if can("portal.view_invoices") or can("portal.make_payments"):
                links["after_login"].append(
                    {"label": "Customer Billing", "url": _safe_reverse("portal:customer_billing_dashboard", default="/portal/customer/billing/")}
                )

    elif role_type == "supplier":
        if can("feature:portal.supplier"):
            links["after_login"].append(
                {"label": "Supplier Portal Dashboard", "url": _safe_reverse("portal:supplier_dashboard", default="/portal/supplier/dashboard/")}
            )
            if can("feature:commerce.purchase"):
                links["after_login"].append(
                    {"label": "Supplier Purchases", "url": _safe_reverse("portal:supplier_purchases_dashboard", default="/portal/supplier/purchases/")}
                )
            if can("portal.view_invoices") or can("portal.make_payments"):
                links["after_login"].append(
                    {"label": "Supplier Billing", "url": _safe_reverse("portal:supplier_billing_dashboard", default="/portal/supplier/billing/")}
                )

    elif role_type == "vendor":
        # Storefront vendor dashboard if vendor link exists
        try:
            seller = getattr(member, "seller", None)
            sub = getattr(seller, "subdomain", None) if seller else None
            if sub:
                links["after_login"].append({"label": "Vendor Dashboard", "url": _safe_reverse("vendor-dashboard-ui", args=[sub])})
        except Exception:
            pass
        if can("feature:commerce.orders") or can("feature:commerce.inventory"):
            links["after_login"].append(
                {"label": "Commerce Dashboard", "url": _safe_reverse("billing:commerce_dashboard", default="/billing/commerce-dashboard/")}
            )

    elif role_type == "field_agent":
        if can("feature:field.agents"):
            links["after_login"].append(
                {"label": "Field Agent Panel", "url": _safe_reverse("khataapp:field_agent_list", default="/khataapp/agents/manage/")}
            )

    elif role_type == "sub_user":
        links["after_login"].append(
            {"label": "Profile / Settings", "url": _safe_reverse("accounts:edit_profile", default="/accounts/dashboard/edit/")}
        )

    return links


def _member_activity_snapshot(member) -> dict:
    snapshot = {
        "parties": 0,
        "transactions": 0,
        "total_credit": 0.0,
        "total_debit": 0.0,
    }
    try:
        from khataapp.models import Party, Transaction
        from django.db.models import Sum

        parties_qs = Party.objects.filter(owner=member)
        snapshot["parties"] = parties_qs.count()
        tx_qs = Transaction.objects.filter(party__owner=member)
        snapshot["transactions"] = tx_qs.count()

        sums = tx_qs.values("txn_type").annotate(total=Sum("amount"))
        for row in sums:
            if row.get("txn_type") == "credit":
                snapshot["total_credit"] = float(row.get("total") or 0)
            elif row.get("txn_type") == "debit":
                snapshot["total_debit"] = float(row.get("total") or 0)
    except Exception:
        pass
    return snapshot


def _razorpay_create_order(gateway: PaymentGateway, invoice: BillingInvoice) -> tuple[bool, dict]:
    """
    Create Razorpay order using REST API. Returns (ok, payload).
    """
    key_id = (gateway.api_key or "").strip()
    key_secret = (gateway.api_secret or "").strip()
    if not key_id or not key_secret:
        return False, {"error": "Razorpay keys missing in admin (api_key/api_secret)."}

    amount = invoice.amount
    try:
        amount_paise = int((Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1")))
    except Exception:
        amount_paise = int(float(amount) * 100)

    data = {
        "amount": max(amount_paise, 100),  # minimum 1 INR
        "currency": "INR",
        "receipt": invoice.invoice_number,
        "notes": {"plan_id": str(invoice.plan_id), "invoice_id": str(invoice.id)},
    }
    try:
        resp = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(key_id, key_secret),
            json=data,
            timeout=12,
        )
        if not resp.ok:
            return False, {"error": f"Razorpay order create failed ({resp.status_code}).", "details": resp.text}
        body = resp.json()
        order_id = body.get("id") or ""
        if not order_id:
            return False, {"error": "Razorpay did not return order id.", "details": body}
        return True, {"order_id": order_id, "amount": data["amount"], "currency": "INR"}
    except Exception as exc:
        return False, {"error": "Razorpay request failed.", "details": str(exc)}


def _razorpay_verify_signature(gateway: PaymentGateway, order_id: str, payment_id: str, signature: str) -> bool:
    key_secret = (gateway.api_secret or "").strip()
    if not key_secret or not order_id or not payment_id or not signature:
        return False
    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").strip())

# --------------------------------------------------------------------------------
# CUSTOM LOGIN HANDLER (Role-Based Redirect)
# --------------------------------------------------------------------------------
def login_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)

        if user:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            # ✅ Role-based redirect
            if user.is_superuser:
                return redirect("/admin/")  # Full admin
            elif user.is_staff:
                return redirect("billing:dashboard")  # Staff dashboard
            else:
                return redirect("billing:commerce_dashboard")  # Normal user dashboard
        else:
            messages.error(request, "Invalid credentials.")
            return redirect("login")

    return render(request, "billing/login.html")


# --------------------------------------------------------------------------------
# PLAN SELECTION
# --------------------------------------------------------------------------------
@login_required
def choose_plan(request):
    plans = Plan.objects.filter(active=True)

    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        if plan_id:
            try:
                plan = Plan.objects.get(id=plan_id)
                profile = request.user.userprofile
                profile.plan = plan
                profile.save()

                # ✅ Free plan → activate immediately
                if plan.is_free or plan.price == 0:
                    invoice = BillingInvoice.objects.create(
                        user=request.user,
                        plan=plan,
                        amount=0,
                        paid=True,
                        status="paid"
                    )
                    Subscription.objects.create(
                        user=request.user,
                        plan=plan,
                        invoice=invoice,
                        status="active",
                        start_date=timezone.now()
                    )
                    messages.success(request, f"'{plan.name}' plan activated (Free).")
                    return redirect("billing:dashboard")
                else:
                    # ✅ Paid plan → go to checkout
                    return redirect(f"/billing/checkout/?plan_id={plan.id}")

            except Plan.DoesNotExist:
                messages.error(request, "Selected plan does not exist.")
                return redirect("billing:choose_plan")

    return render(request, "billing/choose_plan.html", {"plans": plans})


# --------------------------------------------------------------------------------
# CHECKOUT PAGE
# --------------------------------------------------------------------------------
@login_required
def checkout(request):
    plan_id = request.GET.get("plan_id")
    plan = get_object_or_404(Plan, id=plan_id)

    invoice = BillingInvoice.objects.filter(
        user=request.user,
        plan=plan,
        status="unpaid",
    ).order_by("-created_at").first()
    if not invoice:
        invoice = BillingInvoice.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.price_monthly or plan.price,
            status="unpaid",
        )

    razorpay_ctx = None

    # Optional auto-gateway for landing CTAs after public-checkout.
    auto = (request.GET.get("auto") or "").strip()
    if request.method == "GET" and auto:
        gateway = PaymentGateway.objects.filter(active=True).order_by("-provider", "id").first()
        if gateway and gateway.provider == "razorpay":
            ok, payload = _razorpay_create_order(gateway, invoice)
            if ok:
                invoice.payment_reference = payload["order_id"]
                invoice.save(update_fields=["payment_reference"])
                razorpay_ctx = {
                    "key_id": (gateway.api_key or "").strip(),
                    "order_id": payload["order_id"],
                    "amount": payload["amount"],
                    "currency": payload["currency"],
                }
            else:
                messages.error(request, payload.get("error") or "Razorpay is not available.")

    if request.method == "POST":
        gateway_id = request.POST.get("gateway_id")
        gateway = PaymentGateway.objects.filter(id=gateway_id, active=True).first()
        if not gateway:
            messages.error(request, "Please select an active payment gateway.")
            return redirect(f"/billing/checkout/?plan_id={plan.id}")

        # Dummy flow (simulate success)
        if gateway.provider == "dummy":
            invoice.paid = True
            invoice.status = "paid"
            invoice.payment_reference = "dummy"
            invoice.save(update_fields=["paid", "status", "payment_reference"])
            upgrade_subscription(request.user, plan)
            return redirect("billing:payment-success", plan_id=plan.id)

        if gateway.provider == "razorpay":
            ok, payload = _razorpay_create_order(gateway, invoice)
            if not ok:
                messages.error(request, payload.get("error") or "Razorpay is not available.")
                return redirect(f"/billing/checkout/?plan_id={plan.id}")
            invoice.payment_reference = payload["order_id"]
            invoice.save(update_fields=["payment_reference"])
            razorpay_ctx = {
                "key_id": (gateway.api_key or "").strip(),
                "order_id": payload["order_id"],
                "amount": payload["amount"],
                "currency": payload["currency"],
            }
            gateways = PaymentGateway.objects.filter(active=True)
            return render(
                request,
                "billing/checkout.html",
                {"plan": plan, "invoice": invoice, "gateways": gateways, "razorpay": razorpay_ctx, "selected_gateway_id": gateway.id},
            )

        # Real gateway placeholder
        messages.info(request, f"Proceed to {gateway.name} payment. (Integration pending)")
        return redirect("billing:checkout")  # stay on page

    gateways = PaymentGateway.objects.filter(active=True)
    return render(request, "billing/checkout.html", {
        "plan": plan,
        "invoice": invoice,
        "gateways": gateways,
        "razorpay": razorpay_ctx,
    })


def public_checkout(request):
    """
    Public checkout used from landing page Pay Now.

    Creates a lightweight user (OTP bypass) and logs them in so the normal
    billing checkout can proceed even when DESKTOP_MODE is off.
    """
    plan_id = request.GET.get("plan_id") or request.POST.get("plan_id")
    plan = get_object_or_404(Plan, id=plan_id)

    if request.user.is_authenticated:
        return redirect(f"/billing/checkout/?plan_id={plan.id}&auto=1")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        mobile = (request.POST.get("mobile") or "").strip()

        if not email or "@" not in email:
            messages.error(request, "Please enter a valid email.")
            return redirect(f"/billing/public-checkout/?plan_id={plan.id}")
        if not mobile or len("".join([c for c in mobile if c.isdigit()])) < 10:
            messages.error(request, "Please enter a valid mobile number.")
            return redirect(f"/billing/public-checkout/?plan_id={plan.id}")

        # If user already exists, ask them to login (avoid hijacking).
        existing = User.objects.filter(email=email).first() or User.objects.filter(mobile=mobile).first()
        if existing:
            next_url = f"/billing/checkout/?plan_id={plan.id}&auto=1"
            return redirect(f"/accounts/login/?next={next_url}")

        password = get_random_string(16)
        user = User(email=email, username=(name or email.split("@")[0]), mobile=mobile)
        user.set_password(password)
        user.is_active = True
        # mark verified to avoid OTP flow for landing payments
        for attr in ("is_otp_verified", "email_verified", "mobile_verified"):
            if hasattr(user, attr):
                setattr(user, attr, True)
        user.save()

        try:
            KhataProfile.objects.get_or_create(
                user=user,
                defaults={
                    "created_from": "signup",
                    "mobile": mobile,
                    "full_name": name or (user.username or ""),
                },
            )
        except Exception:
            pass

        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)
        return redirect(f"/billing/checkout/?plan_id={plan.id}&auto=1")

    return render(request, "billing/public_checkout.html", {"plan": plan, "hide_sidebar": True})


@csrf_exempt
@login_required
@require_POST
def razorpay_verify(request):
    """
    Verify Razorpay payment signature sent from checkout.js handler.
    """
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8", errors="ignore") or "{}")
    except Exception:
        payload = {}

    order_id = (payload.get("razorpay_order_id") or "").strip()
    payment_id = (payload.get("razorpay_payment_id") or "").strip()
    signature = (payload.get("razorpay_signature") or "").strip()
    plan_id = payload.get("plan_id")

    if not (order_id and payment_id and signature and plan_id):
        return JsonResponse({"ok": False, "message": "Missing payment fields."}, status=400)

    gateway = PaymentGateway.objects.filter(provider="razorpay", active=True).first()
    if not gateway:
        return JsonResponse({"ok": False, "message": "Razorpay gateway not configured."}, status=400)

    if not _razorpay_verify_signature(gateway, order_id, payment_id, signature):
        return JsonResponse({"ok": False, "message": "Payment verification failed."}, status=400)

    invoice = BillingInvoice.objects.filter(user=request.user, plan_id=plan_id, payment_reference=order_id).order_by("-created_at").first()
    if not invoice:
        return JsonResponse({"ok": False, "message": "Invoice not found."}, status=404)

    invoice.paid = True
    invoice.status = "paid"
    invoice.save(update_fields=["paid", "status"])

    try:
        plan = Plan.objects.get(id=plan_id)
        upgrade_subscription(request.user, plan)
    except Exception:
        pass

    return JsonResponse({"ok": True, "redirect_url": reverse("billing:payment-success", kwargs={"plan_id": int(plan_id)})})


# --------------------------------------------------------------------------------
# PAYMENT SUCCESS PAGE
# --------------------------------------------------------------------------------
@login_required
def payment_success(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    upgrade_subscription(request.user, plan)
    latest_invoice = BillingInvoice.objects.filter(user=request.user, plan=plan).order_by("-created_at").first()
    return render(request, "billing/payment_success.html", {"plan": plan, "invoice": latest_invoice})


# --------------------------------------------------------------------------------
# BILLING DASHBOARD (Plan + User Management)
# --------------------------------------------------------------------------------
@login_required
def dashboard(request):
    """
    Billing dashboard.

    - Shows plan/subscription/invoices for everyone.
    - Shows "Manage Users" for billing managers (Admin/Staff/has permission).
    """
    user = request.user
    can_manage_users = _can_manage_linked_users(user)
    linked_users = _linked_users_qs(user)[:12] if can_manage_users else User.objects.none()
    linked_users_count = _linked_users_qs(user).count() if can_manage_users else 0
    linked_by_role = []
    if can_manage_users:
        try:
            linked_by_role = list(
                _linked_users_qs(user)
                .values("billing_role_type")
                .order_by("billing_role_type")
                .annotate(total=Count("id"))
            )
        except Exception:
            linked_by_role = []

    plans = Plan.objects.filter(active=True).order_by("price")
    invoices = request.user.billing_invoices.all().order_by("-created_at")[:10]
    subscriptions = request.user.billing_subscriptions.all().order_by("-created_at")[:5]

    plan = None
    can_add_commerce = False
    try:
        plan = get_effective_plan(user)
        can_add_commerce = bool(getattr(getattr(plan, "feature_toggle", None), "allow_commerce", False))
    except Exception:
        plan = None

    try:
        from billing.hierarchy import billing_hierarchy_config

        hierarchy_cfg = billing_hierarchy_config()
    except Exception:
        hierarchy_cfg = {}

    return render(request, "billing/dashboard.html", {
        "plans": plans,
        "invoices": invoices,
        "subscriptions": subscriptions,
        "can_manage_users": can_manage_users,
        "linked_users": linked_users,
        "linked_users_count": linked_users_count,
        "linked_by_role": linked_by_role,
        "can_add_commerce": can_add_commerce,
        "effective_plan": plan,
        "hierarchy_cfg": hierarchy_cfg,
    })


# --------------------------------------------------------------------------------
# LINKED USERS (Billing Profile -> Manage All Users)
# --------------------------------------------------------------------------------
@login_required
def users_manage(request):
    user = request.user
    if not _can_manage_linked_users(user):
        return HttpResponse("Forbidden", status=403)

    qs = _linked_users_qs(user)
    role_type = (request.GET.get("role_type") or "").strip()
    q = (request.GET.get("q") or "").strip()

    if role_type:
        qs = qs.filter(billing_role_type=role_type)
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(username__icontains=q) | Q(mobile__icontains=q))

    counts = qs.values("billing_role_type").order_by("billing_role_type").annotate(total=Count("id"))
    return render(
        request,
        "billing/users_list.html",
        {
            "linked_users": qs[:200],
            "counts": list(counts),
            "role_type": role_type,
            "q": q,
        },
    )


@login_required
def users_create(request):
    owner = request.user
    if not _can_manage_linked_users(owner):
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        form = LinkedBillingUserForm(request.POST, owner=owner)
        if form.is_valid():
            member = form.save()
            messages.success(request, f"User created: {member.email}")
            return redirect("billing:users_manage")
        messages.error(request, "Please fix the errors below.")
    else:
        form = LinkedBillingUserForm(owner=owner)

    return render(request, "billing/user_form.html", {"form": form, "mode": "create"})


@login_required
def users_edit(request, user_id: int):
    owner = request.user
    if not _can_manage_linked_users(owner):
        return HttpResponse("Forbidden", status=403)

    member = get_object_or_404(User, id=int(user_id), parent=owner)

    # Preload feature overrides for display (safe, best-effort)
    try:
        ensure_user_feature_overrides(member, sync_plan=True)
    except Exception:
        pass

    # Allow-list permissions toggles (stored in member.permissions_json)
    permission_toggles = [
        ("portal.view_invoices", "View Invoices"),
        ("portal.view_reports", "View Reports"),
        ("portal.place_orders", "Place Orders"),
        ("portal.make_payments", "Make Payments"),
        ("billing.user.view_reports", "Billing Reports (Org)"),
        ("billing.user.manage_billing", "Manage Billing"),
        ("billing.user.manage_subusers", "Manage Sub Users"),
        ("billing.user.manage_locations", "Manage Locations"),
        ("billing.user.manage_api_keys", "Manage API Keys"),
    ]

    def _get_perm_state(u, key: str) -> bool:
        try:
            return bool(u.has_permission(key))
        except Exception:
            blob = getattr(u, "permissions_json", None) or {}
            return bool(isinstance(blob, dict) and blob.get(key) in {True, 1, "1", "true", "yes", "on"})

    feature_groups = ["Portal", "Billing", "Commerce", "Inventory", "Advanced"]
    features = list(
        FeatureRegistry.objects.filter(active=True, group__in=feature_groups).order_by("group", "sort_order", "id")[:80]
    )
    overrides = {
        o.feature_id: o
        for o in UserFeatureOverride.objects.filter(user=member, feature__in=features).select_related("feature")
    }
    try:
        from billing.services import user_has_feature
    except Exception:
        user_has_feature = None

    feature_rows = []
    for f in features:
        ov = overrides.get(f.id)
        effective = False
        try:
            effective = bool(user_has_feature(member, f.key)) if user_has_feature else bool(ov.is_enabled if ov else False)
        except Exception:
            effective = bool(ov.is_enabled) if ov else False
        feature_rows.append(
            {
                "id": f.id,
                "group": f.group,
                "label": f.label,
                "key": f.key,
                "effective": effective,
                "overridden": bool(ov and (ov.note or "").strip().lower() == "manual"),
            }
        )
    feature_key_to_id = {row["key"]: int(row["id"]) for row in feature_rows if row.get("key") and row.get("id")}

    # Quick presets: simplified role + permission setup
    quick_presets = [
        {
            "id": "customer_basic",
            "label": "Customer (Basic)",
            "desc": "Customer portal + view invoices + place orders",
            "perm_on": ["portal.view_invoices", "portal.place_orders"],
            "perm_off": ["portal.make_payments", "portal.view_reports"],
            "feature_on": ["portal.customer"],
            "feature_off": ["portal.supplier"],
        },
        {
            "id": "customer_full",
            "label": "Customer (Full)",
            "desc": "Customer portal + invoices + orders + payments + reports",
            "perm_on": ["portal.view_invoices", "portal.place_orders", "portal.make_payments", "portal.view_reports"],
            "perm_off": [],
            "feature_on": ["portal.customer", "portal.payments"],
            "feature_off": ["portal.supplier"],
        },
        {
            "id": "supplier_basic",
            "label": "Supplier (Basic)",
            "desc": "Supplier portal + purchases + billing view",
            "perm_on": ["portal.view_invoices"],
            "perm_off": ["portal.place_orders"],
            "feature_on": ["portal.supplier", "commerce.purchase"],
            "feature_off": ["portal.customer"],
        },
        {
            "id": "vendor_basic",
            "label": "Vendor (Basic)",
            "desc": "Commerce orders + inventory",
            "perm_on": [],
            "perm_off": [],
            "feature_on": ["commerce.orders", "commerce.inventory"],
            "feature_off": [],
        },
        {
            "id": "field_agent_basic",
            "label": "Field Agent (Basic)",
            "desc": "Field agent module access",
            "perm_on": [],
            "perm_off": [],
            "feature_on": ["field.agents"],
            "feature_off": [],
        },
        {
            "id": "sub_user_viewer",
            "label": "Sub User (Viewer)",
            "desc": "Read-only basic access (no portal actions)",
            "perm_on": [],
            "perm_off": ["portal.place_orders", "portal.make_payments"],
            "feature_on": [],
            "feature_off": ["portal.customer", "portal.supplier"],
        },
    ]

    action = (request.POST.get("action") or "").strip().lower() if request.method == "POST" else ""
    if request.method == "POST" and action in {"toggle_active", "reset_password", "send_welcome_kit", "impersonate"}:
        if action == "toggle_active":
            member.is_active = not bool(member.is_active)
            member.save(update_fields=["is_active"])
            messages.success(request, f"Login {'enabled' if member.is_active else 'disabled'} for {member.email}.")
            return redirect("billing:users_edit", user_id=member.id)

        if action == "impersonate":
            # Secure view-as-user: only allow for linked users under the current owner.
            # Store return info in session so we can restore later.
            request.session["impersonator_id"] = owner.id
            request.session["impersonator_return"] = reverse("billing:users_edit", kwargs={"user_id": member.id})
            try:
                from django.contrib.auth import login as auth_login
                from django.conf import settings

                backend = "django.contrib.auth.backends.ModelBackend"
                try:
                    backend = (getattr(settings, "AUTHENTICATION_BACKENDS", None) or [backend])[0]
                except Exception:
                    pass
                auth_login(request, member, backend=backend)
            except Exception:
                return HttpResponse("Unable to impersonate", status=500)

            messages.info(request, f"Viewing as {member.email}. Use 'Return to Admin' to switch back.")
            return redirect("accounts:role_dashboard")

        if action in {"reset_password", "send_welcome_kit"}:
            new_password = secrets.token_urlsafe(10).replace("-", "").replace("_", "")[:12]
            member.set_password(new_password)
            member.is_otp_verified = False
            member.save(update_fields=["password", "is_otp_verified"])

            login_url = _build_abs(request, _safe_reverse("accounts:login", default="/accounts/login/"))
            msg_text = f"Login URL: {login_url}\nUser: {member.email}\nPassword: {new_password}"

            sent = False
            # WhatsApp (best-effort)
            try:
                from khataapp.utils.whatsapp_utils import send_whatsapp_message

                mobile = ""
                try:
                    mobile = (getattr(getattr(member, "khata_profile", None), "mobile", "") or getattr(member, "mobile", "") or "").strip()
                except Exception:
                    mobile = (getattr(member, "mobile", "") or "").strip()
                if mobile:
                    send_whatsapp_message(mobile.lstrip("+"), msg_text)
                    sent = True
            except Exception:
                pass

            # Email (best-effort)
            try:
                from django.core.mail import send_mail
                from django.conf import settings

                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@example.com"
                if member.email:
                    send_mail("Your Login Details", msg_text, from_email, [member.email], fail_silently=True)
                    sent = True
            except Exception:
                pass

            if action == "reset_password":
                messages.success(
                    request,
                    f"Password reset for {member.email}. "
                    + ("Welcome kit sent." if sent else f"New password: {new_password}"),
                )
            else:
                messages.success(
                    request,
                    f"Welcome kit regenerated for {member.email}. "
                    + ("Sent." if sent else f"New password: {new_password}"),
                )
            return redirect("billing:users_edit", user_id=member.id)

    if request.method == "POST":
        form = LinkedBillingUserForm(request.POST, owner=owner, instance=member)
        if form.is_valid():
            member = form.save()

            # Save permission toggles
            blob = getattr(member, "permissions_json", None) or {}
            if not isinstance(blob, dict):
                blob = {}
            for key, _label in permission_toggles:
                posted = (request.POST.get(f"perm__{key}") or "").strip().lower() in {"1", "true", "yes", "on"}
                if posted:
                    blob[key] = True
                else:
                    # keep explicit False to override role defaults if needed
                    blob[key] = False
            member.permissions_json = blob
            member.save(update_fields=["permissions_json"])

            # Save feature overrides (Features & Services)
            features_by_id = {f.id: f for f in features}
            for row in feature_rows:
                fid = int(row["id"])
                f = features_by_id.get(fid)
                if not f:
                    continue
                posted = (request.POST.get(f"feature__{fid}") or "").strip().lower() in {"1", "true", "yes", "on"}
                UserFeatureOverride.objects.update_or_create(
                    user=member,
                    feature=f,
                    defaults={"is_enabled": posted, "note": "manual"},
                )

            messages.success(request, f"User updated: {member.email}")
            return redirect("billing:users_edit", user_id=member.id)
        messages.error(request, "Please fix the errors below.")
    else:
        form = LinkedBillingUserForm(owner=owner, instance=member)

    # Trace + working history (best-effort)
    trace = {
        "owner_id": getattr(owner, "id", None),
        "member_parent_id": getattr(getattr(member, "parent", None), "id", None),
        "children_count": 0,
    }
    try:
        trace["children_count"] = User.objects.filter(parent=member).count()
    except Exception:
        trace["children_count"] = 0

    recent = {
        "parties": [],
        "transactions": [],
        "orders": [],
        "invoices": [],
        "payments": [],
    }
    totals = {
        "parties": 0,
        "transactions": 0,
        "orders": 0,
        "invoices": 0,
        "payments": 0,
    }
    try:
        from khataapp.models import Party, Transaction

        totals["parties"] = Party.objects.filter(owner=member).count()
        totals["transactions"] = Transaction.objects.filter(party__owner=member).count()
        recent["parties"] = list(Party.objects.filter(owner=member).order_by("-id")[:8])
        recent["transactions"] = list(
            Transaction.objects.filter(party__owner=member).select_related("party").order_by("-id")[:12]
        )
    except Exception:
        pass

    try:
        totals["orders"] = Order.objects.filter(user=member).count()
        totals["invoices"] = BillingInvoice.objects.filter(user=member).count()
        # payments can be user-based or order-based in some schemas; billing.models exposes Payment and Order
        payment_field_names = {f.name for f in Payment._meta.get_fields()}
        if "user" in payment_field_names:
            totals["payments"] = Payment.objects.filter(user=member).count()
            recent["payments"] = list(Payment.objects.filter(user=member).order_by("-created_at", "-id")[:10])
        elif "order" in payment_field_names:
            totals["payments"] = Payment.objects.filter(order__user=member).count()
            recent["payments"] = list(Payment.objects.filter(order__user=member).order_by("-created_at", "-id")[:10])
        recent["orders"] = list(Order.objects.filter(user=member).order_by("-created_at", "-id")[:10])
        recent["invoices"] = list(BillingInvoice.objects.filter(user=member).order_by("-created_at", "-id")[:10])
    except Exception:
        pass

    context = {
        "form": form,
        "mode": "edit",
        "member": member,
        "login_url": _build_abs(request, _safe_reverse("accounts:login", default="/accounts/login/")),
        "portal_links": _allowed_links_for_user(request, member),
        "permission_toggles": [
            {"key": key, "label": label, "enabled": _get_perm_state(member, key)}
            for key, label in permission_toggles
        ],
        "feature_rows": feature_rows,
        "perm_enabled_count": sum(1 for key, _label in permission_toggles if _get_perm_state(member, key)),
        "perm_total_count": len(permission_toggles),
        "feature_enabled_count": sum(1 for f in feature_rows if f.get("effective")),
        "feature_total_count": len(feature_rows),
        "feature_key_to_id": feature_key_to_id,
        "quick_presets": quick_presets,
        "activity": _member_activity_snapshot(member),
        "subscription_events": list(
            SubscriptionHistory.objects.filter(user=member).select_related("plan").order_by("-created_at")[:10]
        ),
        "trace": trace,
        "totals": totals,
        "recent": recent,
        "can_impersonate": True,
    }
    return render(request, "billing/user_form.html", context)


@login_required
def impersonate_stop(request):
    """
    Restore admin session after view-as-user.
    """
    impersonator_id = request.session.get("impersonator_id")
    if not impersonator_id:
        return redirect("accounts:role_dashboard")

    try:
        impersonator = User.objects.get(id=int(impersonator_id))
    except Exception:
        impersonator = None

    try:
        from django.contrib.auth import login as auth_login
        from django.conf import settings

        if impersonator:
            backend = "django.contrib.auth.backends.ModelBackend"
            try:
                backend = (getattr(settings, "AUTHENTICATION_BACKENDS", None) or [backend])[0]
            except Exception:
                pass
            auth_login(request, impersonator, backend=backend)
    except Exception:
        pass

    return_to = request.session.get("impersonator_return") or reverse("billing:users_manage")
    try:
        del request.session["impersonator_id"]
    except Exception:
        pass
    try:
        del request.session["impersonator_return"]
    except Exception:
        pass

    messages.info(request, "Returned to admin session.")
    return redirect(return_to)


# --------------------------------------------------------------------------------
# WEBHOOK HANDLERS (Razorpay, PhonePe, Dummy)
# --------------------------------------------------------------------------------
@csrf_exempt
def gateway_webhook(request, provider):
    gateway = PaymentGateway.objects.filter(provider=provider, active=True).first()
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    # ✅ Razorpay
    if provider == "razorpay":
        payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
        order_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")
        status = payload.get("event")

        invoice = BillingInvoice.objects.filter(payment_reference=order_id).first()
        if invoice and "captured" in str(status).lower():
            invoice.paid = True
            invoice.payment_reference = payment_id
            invoice.save(update_fields=["paid", "payment_reference"])
            Subscription.objects.filter(invoice=invoice).update(status="active", start_date=timezone.now())
            return HttpResponse(status=200)
        return HttpResponse(status=400)

    # ✅ PhonePe
    if provider == "phonepe":
        invoice_number = payload.get("transactionId")
        status = payload.get("status")
        invoice = BillingInvoice.objects.filter(number=invoice_number).first()
        if invoice and status == "SUCCESS":
            invoice.paid = True
            invoice.save(update_fields=["paid"])
            Subscription.objects.filter(invoice=invoice).update(status="active", start_date=timezone.now())
            return HttpResponse(status=200)
        return HttpResponse(status=400)

    # ✅ Dummy
    if provider == "dummy":
        inv_id = payload.get("invoice_id")
        invoice = BillingInvoice.objects.filter(id=inv_id).first()
        if not invoice:
            return HttpResponse(status=404)
        if payload.get("status") in ("paid", "success"):
            invoice.paid = True
            invoice.payment_reference = payload.get("payment_ref", "dummy")
            invoice.save(update_fields=["paid", "payment_reference"])
            Subscription.objects.filter(invoice=invoice).update(status="active", start_date=timezone.now())
        else:
            invoice.paid = False
            invoice.save(update_fields=["paid"])
            Subscription.objects.filter(invoice=invoice).update(status="cancelled")
        return HttpResponse(status=200)

    return HttpResponse(status=400)


# --------------------------------------------------------------------------------
# PLAN UPGRADE PAGE
# --------------------------------------------------------------------------------
@login_required
def upgrade_plan(request):
    user = request.user
    plans = Plan.objects.all().order_by("price")
    current_plan = getattr(getattr(user, "userprofile", None), "plan", None)

    return render(request, "billing/upgrade_plan.html", {
        "plans": plans,
        "current_plan": current_plan
    })


# --------------------------------------------------------------------------------
# USER PLAN MANAGEMENT (Profile -> Settings -> Plan Management)
# --------------------------------------------------------------------------------
@login_required
def plan_management(request):
    sync_feature_registry()
    plans = Plan.objects.filter(active=True).order_by("price_monthly", "price")
    subscription = get_active_subscription(request.user)
    current_plan = subscription.plan if subscription else None
    features = FeatureRegistry.objects.filter(active=True)
    plan_features = {}
    for plan in plans:
        plan_features[plan.id] = set(
            PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature_id", flat=True)
        )
    return render(request, "billing/plan_management.html", {
        "plans": plans,
        "current_plan": current_plan,
        "features": features,
        "plan_features": plan_features,
    })


@login_required
@require_POST
def start_upgrade(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id, active=True)
    invoice = BillingInvoice.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price_monthly or plan.price,
        status="unpaid",
    )
    SubscriptionHistory.objects.create(
        user=request.user,
        plan=plan,
        event_type="payment",
        details={"invoice_id": invoice.id, "source": "start_upgrade"},
    )
    return redirect(f"/billing/checkout/?plan_id={plan.id}")


# --------------------------------------------------------------------------------
# ADMIN FEATURE MATRIX
# --------------------------------------------------------------------------------
@login_required
def feature_matrix(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponse("Admin access required", status=403)
    sync_feature_registry()
    plans = Plan.objects.filter(active=True).order_by("price_monthly", "price")
    features = FeatureRegistry.objects.filter(active=True)
    matrix = {}
    for plan in plans:
        enabled = set(
            PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature_id", flat=True)
        )
        matrix[plan.id] = enabled
    return render(request, "billing/feature_matrix.html", {
        "plans": plans,
        "features": features,
        "matrix": matrix,
    })


@login_required
@require_POST
def feature_matrix_save(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponse("Admin access required", status=403)
    sync_feature_registry()
    payload = json.loads(request.body.decode("utf-8"))
    plan_id = payload.get("plan_id")
    feature_ids = payload.get("feature_ids", [])
    plan = get_object_or_404(Plan, id=plan_id)
    PlanFeature.objects.filter(plan=plan).exclude(feature_id__in=feature_ids).delete()
    for feature_id in feature_ids:
        PlanFeature.objects.update_or_create(
            plan=plan,
            feature_id=feature_id,
            defaults={"enabled": True},
        )
    return HttpResponse(status=204)


# --------------------------------------------------------------------------------
# COMMERCE DASHBOARD (Normal User Side)
# --------------------------------------------------------------------------------
@login_required
def commerce_dashboard(request):
    """
    Display commerce data if user's plan allows.
    Free plan → view-only mode
    Paid plan → full access
    """
    user = request.user
    try:
        from billing.services import get_effective_plan

        plan = get_effective_plan(user)
    except Exception:
        profile = getattr(user, "userprofile", None)
        plan = getattr(profile, "plan", None)

    is_paid = bool(plan and not getattr(plan, "is_free", False))

    invoices_qs = BillingInvoice.objects.filter(user=user)
    orders_qs = Order.objects.filter(user=user)
    order_items_qs = OrderItem.objects.filter(order__user=user)

    payment_field_names = {f.name for f in Payment._meta.get_fields()}
    if "user" in payment_field_names:
        payments_qs = Payment.objects.filter(user=user)
    elif "order" in payment_field_names:
        payments_qs = Payment.objects.filter(order__user=user)
    else:
        payments_qs = Payment.objects.none()

    threads_qs = ChatThread.objects.filter(Q(user1=user) | Q(user2=user))
    chats_qs = ChatMessage.objects.filter(thread__in=threads_qs).select_related("thread", "sender")

    context = {
        "is_paid": is_paid,
        "plan": plan,
        "invoices": invoices_qs,
        "payments": payments_qs,
        "orders": orders_qs,
        "order_items": order_items_qs,
        "warehouses": Warehouse.objects.all(),
        "stocks": Stock.objects.all(),
        "chats": chats_qs,
        "threads": threads_qs,
        "notifications": Notification.objects.filter(user=user),
        "portals": PartyPortal.objects.all(),
    }

    return render(request, "billing/commerce_dashboard.html", context)


@login_required
def billing_history(request):
    invoices = BillingInvoice.objects.filter(user=request.user).order_by("-created_at")
    subscriptions = Subscription.objects.filter(user=request.user).order_by("-created_at")
    events = SubscriptionHistory.objects.filter(user=request.user).order_by("-created_at")[:50]
    return render(request, "billing/history.html", {
        "invoices": invoices,
        "subscriptions": subscriptions,
        "events": events,
    })
