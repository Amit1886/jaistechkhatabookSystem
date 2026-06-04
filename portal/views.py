from __future__ import annotations

import json
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, DecimalField, F, Max, Sum
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.roles import can_edit
from accounts.utils import render_to_pdf_bytes
from commerce.models import Invoice, Order, OrderItem, Payment, Product
from khataapp.models import Party
from portal.decorators import get_portal_user_from_session, get_portal_user_from_token, portal_login_required
from portal.models import CartItem, PaymentLink, PortalOrder, PortalPermission, PortalUser
from portal.services import (
    DEFAULT_PERMISSION_KEYS,
    create_portal_account_for_party,
    customer_portal_enabled,
    portal_base_url,
    portal_enabled,
    supplier_portal_enabled,
)

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def portal_home(request: HttpRequest):
    pu = get_portal_user_from_session(request)
    if pu:
        # Respect global enable/disable settings even for the home redirect.
        try:
            if not portal_enabled():
                for k in ("portal_user_id", "portal_role"):
                    try:
                        request.session.pop(k, None)
                    except Exception:
                        pass
                messages.error(request, "Portal is currently disabled.")
                return redirect("accounts:login")
            if pu.role == PortalUser.Role.CUSTOMER and not customer_portal_enabled():
                for k in ("portal_user_id", "portal_role"):
                    try:
                        request.session.pop(k, None)
                    except Exception:
                        pass
                messages.error(request, "Customer portal is currently disabled.")
                return redirect("accounts:login")
            if pu.role == PortalUser.Role.SUPPLIER and not supplier_portal_enabled():
                for k in ("portal_user_id", "portal_role"):
                    try:
                        request.session.pop(k, None)
                    except Exception:
                        pass
                messages.error(request, "Supplier portal is currently disabled.")
                return redirect("accounts:login")
        except Exception:
            pass

        if getattr(pu, "must_change_password", False):
            return redirect("portal:change_password")
        if pu.role == PortalUser.Role.SUPPLIER:
            return redirect("portal:supplier_dashboard")
        return redirect("portal:customer_dashboard")
    return redirect("accounts:login")


def portal_logout(request: HttpRequest):
    for k in ("portal_user_id", "portal_role"):
        try:
            request.session.pop(k, None)
        except Exception:
            pass
    messages.success(request, "Logged out from portal.")
    return redirect("accounts:login")


@portal_login_required()
def change_password(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})

    if request.method == "POST":
        current_password = str(request.POST.get("current_password") or "")
        new_password = str(request.POST.get("new_password") or "")
        confirm_password = str(request.POST.get("confirm_password") or "")

        if not current_password or not portal_user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return render(request, "portal/change_password.html", {"portal_user": portal_user, "portal_perms": portal_perms})

        if len(new_password) < 8:
            messages.error(request, "New password must be at least 8 characters.")
            return render(request, "portal/change_password.html", {"portal_user": portal_user, "portal_perms": portal_perms})

        if new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
            return render(request, "portal/change_password.html", {"portal_user": portal_user, "portal_perms": portal_perms})

        portal_user.set_password(new_password)
        portal_user.must_change_password = False
        portal_user.save(update_fields=["password_hash", "must_change_password", "updated_at"])
        messages.success(request, "Password updated successfully.")

        if portal_user.role == PortalUser.Role.SUPPLIER:
            return redirect("portal:supplier_dashboard")
        return redirect("portal:customer_dashboard")

    return render(request, "portal/change_password.html", {"portal_user": portal_user, "portal_perms": portal_perms})


@portal_login_required(role=PortalUser.Role.CUSTOMER)
def customer_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_orders = portal_perms.get("place_orders", True) is not False
    can_invoices = portal_perms.get("view_invoices", True) is not False
    can_reports = portal_perms.get("view_reports", True) is not False

    orders_qs = Order.objects.filter(owner=owner, party=party, order_type__iexact="sale") if can_orders else Order.objects.none()
    total_orders = orders_qs.count() if can_orders else 0

    inv_qs = (
        Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="sale")
        .select_related("order")
        if can_invoices
        else Invoice.objects.none()
    )
    invoice_total = inv_qs.aggregate(total=Sum("amount"))["total"] if can_invoices else Decimal("0.00")
    invoice_total = invoice_total or Decimal("0.00")
    paid_total = (
        Payment.objects.filter(invoice__in=inv_qs).aggregate(total=Sum("amount")).get("total") if can_invoices else Decimal("0.00")
    )
    paid_total = paid_total or Decimal("0.00")
    outstanding = invoice_total - paid_total if can_invoices else None

    recent_invoices = inv_qs.order_by("-created_at", "-id")[:8] if can_invoices else []
    recent_payments = (
        Payment.objects.filter(invoice__in=inv_qs).select_related("invoice").order_by("-created_at", "-id")[:8] if can_invoices else []
    )
    recent_orders = orders_qs.order_by("-created_at", "-id")[:8] if can_orders else []

    return render(
        request,
        "portal/customer_dashboard.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "total_orders": total_orders,
            "outstanding": outstanding,
            "recent_invoices": recent_invoices,
            "recent_payments": recent_payments,
            "recent_orders": recent_orders,
            "can_orders": can_orders,
            "can_invoices": can_invoices,
            "can_reports": can_reports,
        },
    )


@portal_login_required(role=PortalUser.Role.CUSTOMER)
def customer_ecommerce_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_orders = portal_perms.get("place_orders", True) is not False
    orders_qs = Order.objects.filter(owner=owner, party=party, order_type__iexact="sale") if can_orders else Order.objects.none()
    total_orders = orders_qs.count() if can_orders else 0
    recent_orders = orders_qs.order_by("-created_at", "-id")[:12] if can_orders else []

    cart_count = CartItem.objects.filter(portal_user=portal_user).aggregate(c=Sum("qty")).get("c") or 0 if can_orders else 0

    return render(
        request,
        "portal/customer_dashboard_ecommerce.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "can_orders": can_orders,
            "total_orders": total_orders,
            "recent_orders": recent_orders,
            "cart_count": cart_count,
        },
    )


@portal_login_required(role=PortalUser.Role.CUSTOMER)
def customer_billing_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_invoices = portal_perms.get("view_invoices", True) is not False
    can_reports = portal_perms.get("view_reports", True) is not False
    can_payments = portal_perms.get("make_payments", True) is not False

    inv_qs = (
        Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="sale")
        .select_related("order")
        if can_invoices
        else Invoice.objects.none()
    )
    invoice_total = inv_qs.aggregate(total=Sum("amount"))["total"] if can_invoices else Decimal("0.00")
    invoice_total = invoice_total or Decimal("0.00")
    paid_total = (
        Payment.objects.filter(invoice__in=inv_qs).aggregate(total=Sum("amount")).get("total") if can_invoices else Decimal("0.00")
    )
    paid_total = paid_total or Decimal("0.00")
    outstanding = invoice_total - paid_total if can_invoices else None

    recent_invoices = inv_qs.order_by("-created_at", "-id")[:12] if can_invoices else []
    recent_payments = (
        Payment.objects.filter(invoice__in=inv_qs).select_related("invoice").order_by("-created_at", "-id")[:12] if can_invoices else []
    )

    return render(
        request,
        "portal/customer_dashboard_billing.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "can_invoices": can_invoices,
            "can_reports": can_reports,
            "can_payments": can_payments,
            "outstanding": outstanding,
            "recent_invoices": recent_invoices,
            "recent_payments": recent_payments,
        },
    )


@portal_login_required(role=PortalUser.Role.SUPPLIER)
def supplier_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_purchase_history = portal_perms.get("view_purchase_history", True) is not False
    can_demand_trends = portal_perms.get("view_demand_trends", True) is not False
    can_invoices = portal_perms.get("view_invoices", True) is not False

    purchase_orders = (
        Order.objects.filter(owner=owner, party=party, order_type__iexact="purchase") if can_purchase_history else Order.objects.none()
    )
    total_pos = purchase_orders.count() if can_purchase_history else 0

    purchased_products = []
    demand_trends = []
    product_ids: list[int] = []
    if can_purchase_history:
        purchased_products = list(
            OrderItem.objects.filter(order__in=purchase_orders)
            .values("product_id", "product__name")
            .annotate(total_qty=Sum("qty"), last_purchase=Max("order__created_at"))
            .order_by("-last_purchase")[:20]
        )
        product_ids = [p["product_id"] for p in purchased_products if p.get("product_id")]

    if can_demand_trends and product_ids:
        since = timezone.now() - timedelta(days=30)
        demand_trends = list(
            OrderItem.objects.filter(
                order__owner=owner,
                order__order_type__iexact="sale",
                product_id__in=product_ids,
                order__created_at__gte=since,
            )
            .values("product__name")
            .annotate(qty_sold=Sum("qty"))
            .order_by("-qty_sold")[:20]
        )

    inv_qs = (
        Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="purchase").select_related("order")
        if can_invoices
        else Invoice.objects.none()
    )
    recent_invoices = inv_qs.order_by("-created_at", "-id")[:8] if can_invoices else []

    return render(
        request,
        "portal/supplier_dashboard.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "total_purchase_orders": total_pos,
            "purchased_products": purchased_products,
            "demand_trends": demand_trends,
            "recent_invoices": recent_invoices,
            "can_purchase_history": can_purchase_history,
            "can_demand_trends": can_demand_trends,
            "can_invoices": can_invoices,
        },
    )


@portal_login_required(role=PortalUser.Role.SUPPLIER)
def supplier_purchases_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_purchase_history = portal_perms.get("view_purchase_history", True) is not False
    can_demand_trends = portal_perms.get("view_demand_trends", True) is not False

    purchase_orders = (
        Order.objects.filter(owner=owner, party=party, order_type__iexact="purchase") if can_purchase_history else Order.objects.none()
    )
    total_pos = purchase_orders.count() if can_purchase_history else 0
    recent_pos = purchase_orders.order_by("-created_at", "-id")[:12] if can_purchase_history else []

    purchased_products = []
    demand_trends = []
    product_ids: list[int] = []
    if can_purchase_history:
        purchased_products = list(
            OrderItem.objects.filter(order__in=purchase_orders)
            .values("product_id", "product__name")
            .annotate(total_qty=Sum("qty"), last_purchase=Max("order__created_at"))
            .order_by("-last_purchase")[:20]
        )
        product_ids = [p["product_id"] for p in purchased_products if p.get("product_id")]

    if can_demand_trends and product_ids:
        since = timezone.now() - timedelta(days=30)
        demand_trends = list(
            OrderItem.objects.filter(
                order__owner=owner,
                order__order_type__iexact="sale",
                product_id__in=product_ids,
                order__created_at__gte=since,
            )
            .values("product__name")
            .annotate(qty_sold=Sum("qty"))
            .order_by("-qty_sold")[:20]
        )

    return render(
        request,
        "portal/supplier_dashboard_purchases.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "total_purchase_orders": total_pos,
            "recent_purchase_orders": recent_pos,
            "purchased_products": purchased_products,
            "demand_trends": demand_trends,
            "can_purchase_history": can_purchase_history,
            "can_demand_trends": can_demand_trends,
        },
    )


@portal_login_required(role=PortalUser.Role.SUPPLIER)
def supplier_billing_dashboard(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    can_invoices = portal_perms.get("view_invoices", True) is not False
    can_reports = portal_perms.get("view_reports", True) is not False

    inv_qs = (
        Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="purchase").select_related("order")
        if can_invoices
        else Invoice.objects.none()
    )
    recent_invoices = inv_qs.order_by("-created_at", "-id")[:12] if can_invoices else []
    recent_payments = (
        Payment.objects.filter(invoice__in=inv_qs).select_related("invoice").order_by("-created_at", "-id")[:12] if can_invoices else []
    )

    invoice_total = inv_qs.aggregate(total=Sum("amount"))["total"] if can_invoices else Decimal("0.00")
    invoice_total = invoice_total or Decimal("0.00")
    paid_total = (
        Payment.objects.filter(invoice__in=inv_qs).aggregate(total=Sum("amount")).get("total") if can_invoices else Decimal("0.00")
    )
    paid_total = paid_total or Decimal("0.00")
    outstanding = invoice_total - paid_total if can_invoices else None

    return render(
        request,
        "portal/supplier_dashboard_billing.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "party": party,
            "can_invoices": can_invoices,
            "can_reports": can_reports,
            "outstanding": outstanding,
            "recent_invoices": recent_invoices,
            "recent_payments": recent_payments,
        },
    )


@portal_login_required(role=PortalUser.Role.CUSTOMER, permission="place_orders")
def catalog(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    owner = portal_user.owner
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.filter(owner=owner).order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)

    cart_count = CartItem.objects.filter(portal_user=portal_user).aggregate(c=Sum("qty")).get("c") or 0
    return render(
        request,
        "portal/catalog.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "products": qs[:200], "q": q, "cart_count": cart_count},
    )


@portal_login_required(role=PortalUser.Role.CUSTOMER, permission="place_orders")
def product_detail(request: HttpRequest, product_id: int):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    owner = portal_user.owner
    product = get_object_or_404(Product, id=product_id, owner=owner)
    in_cart = CartItem.objects.filter(portal_user=portal_user, product=product).first()
    return render(
        request,
        "portal/product_detail.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "product": product, "in_cart": in_cart},
    )


@portal_login_required(role=PortalUser.Role.CUSTOMER, permission="place_orders")
def cart_view(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    items = (
        CartItem.objects.filter(portal_user=portal_user)
        .select_related("product")
        .order_by("-updated_at", "-id")
    )
    subtotal = Decimal("0.00")
    rows = []
    for it in items:
        price = _to_decimal(getattr(it.product, "price", 0))
        line = price * Decimal(int(it.qty or 0))
        subtotal += line
        rows.append({"item": it, "price": price, "line_total": line})

    return render(request, "portal/cart.html", {"portal_user": portal_user, "portal_perms": portal_perms, "rows": rows, "subtotal": subtotal})


@portal_login_required(role=PortalUser.Role.CUSTOMER, permission="place_orders")
def checkout(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    owner = portal_user.owner
    party = portal_user.party

    cart_items = list(CartItem.objects.filter(portal_user=portal_user).select_related("product"))
    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("portal:catalog")

    stock_issues = []
    for it in cart_items:
        prod = getattr(it, "product", None)
        if not prod:
            continue
        available = int(getattr(prod, "stock", 0) or 0)
        desired = int(it.qty or 0)
        if available <= 0:
            stock_issues.append(f"{getattr(prod, 'name', 'Item')} is out of stock.")
        elif desired > available:
            stock_issues.append(f"{getattr(prod, 'name', 'Item')}: only {available} available (requested {desired}).")
    if stock_issues:
        messages.error(request, "Cannot checkout:\n" + "\n".join(stock_issues))
        return redirect("portal:cart")

    if request.method == "POST":
        with transaction.atomic():
            order = Order.objects.create(
                owner=owner,
                party=party,
                order_type="SALE",
                status="pending",
                notes="Placed via Customer Portal",
                order_source="Customer Portal",
            )
            for it in cart_items:
                qty = int(it.qty or 0)
                if qty <= 0:
                    continue
                OrderItem.objects.create(order=order, product=it.product, qty=qty, price=getattr(it.product, "price", 0) or 0)

            order.save()

            po = PortalOrder.objects.create(
                owner=owner,
                portal_user=portal_user,
                party=party,
                commerce_order=order,
                status=PortalOrder.Status.SUBMITTED,
                total_amount=order.total_amount(),
                payload={"source": "customer_portal"},
            )

            CartItem.objects.filter(portal_user=portal_user).delete()

        messages.success(request, f"Order placed successfully (Order #{order.id}).")
        return redirect("portal:order_detail", order_id=order.id)

    # GET confirmation
    subtotal = Decimal("0.00")
    for it in cart_items:
        subtotal += _to_decimal(getattr(it.product, "price", 0)) * Decimal(int(it.qty or 0))
    return render(
        request,
        "portal/checkout.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "cart_items": cart_items, "subtotal": subtotal},
    )


@portal_login_required()
def portal_order_list(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    if portal_user.role == PortalUser.Role.SUPPLIER:
        if portal_perms.get("view_purchase_history", True) is False:
            messages.error(request, "Permission denied.")
            return redirect("portal:supplier_dashboard")
        order_type = "PURCHASE"
    else:
        if portal_perms.get("place_orders", True) is False:
            messages.error(request, "Permission denied.")
            return redirect("portal:customer_dashboard")
        order_type = "SALE"

    qs = Order.objects.filter(owner=owner, party=party, order_type__iexact=order_type).order_by("-created_at", "-id")[:100]
    return render(
        request,
        "portal/order_list.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "orders": qs, "order_type": order_type},
    )


@portal_login_required()
def portal_order_detail(request: HttpRequest, order_id: int):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner
    if portal_user.role == PortalUser.Role.SUPPLIER:
        if portal_perms.get("view_purchase_history", True) is False:
            messages.error(request, "Permission denied.")
            return redirect("portal:supplier_dashboard")
    else:
        if portal_perms.get("place_orders", True) is False:
            messages.error(request, "Permission denied.")
            return redirect("portal:customer_dashboard")
    order = get_object_or_404(Order.objects.select_related("party"), id=order_id, owner=owner, party=party)
    items = order.items.select_related("product").all().order_by("id")
    return render(
        request,
        "portal/order_detail.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "order": order, "items": items},
    )


@portal_login_required(permission="view_invoices")
def portal_invoice_list(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner
    if portal_user.role == PortalUser.Role.SUPPLIER:
        qs = Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="purchase")
    else:
        qs = Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact="sale")
    invoices = qs.select_related("order").order_by("-created_at", "-id")[:100]
    return render(
        request,
        "portal/invoice_list.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "invoices": invoices},
    )


@portal_login_required(permission="view_invoices")
def portal_invoice_detail(request: HttpRequest, invoice_id: int):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner
    invoice = get_object_or_404(Invoice.objects.select_related("order", "order__party").prefetch_related("payments"), id=invoice_id, order__owner=owner, order__party=party)
    items = invoice.order.items.select_related("product").all().order_by("id")
    payments = invoice.payments.all().order_by("-created_at", "-id")
    paid_total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    balance = (invoice.amount or Decimal("0.00")) - paid_total

    can_pay = portal_user.role == PortalUser.Role.CUSTOMER and portal_perms.get("make_payments", True) is not False and balance > 0
    pay_url = ""
    if can_pay:
        pl = (
            PaymentLink.objects.filter(invoice=invoice, status__in=[PaymentLink.Status.CREATED, PaymentLink.Status.OPENED])
            .order_by("-created_at", "-id")
            .first()
        )
        if not pl:
            pl = PaymentLink.objects.create(
                owner=owner,
                invoice=invoice,
                portal_user=portal_user,
                token=secrets_token(),
                amount=invoice.amount or Decimal("0.00"),
                status=PaymentLink.Status.CREATED,
                expires_at=timezone.now() + timedelta(days=7),
            )
        pay_url = request.build_absolute_uri(reverse("portal:pay", args=[pl.token]))
    return render(
        request,
        "portal/invoice_detail.html",
        {
            "portal_user": portal_user,
            "portal_perms": portal_perms,
            "invoice": invoice,
            "items": items,
            "payments": payments,
            "paid_total": paid_total,
            "balance": balance,
            "pay_url": pay_url,
            "can_pay": can_pay,
        },
    )


@portal_login_required(permission="view_invoices")
def portal_payment_list(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})
    party = portal_user.party
    owner = portal_user.owner

    order_type = "purchase" if portal_user.role == PortalUser.Role.SUPPLIER else "sale"
    inv_qs = Invoice.objects.filter(order__owner=owner, order__party=party, order__order_type__iexact=order_type)
    payments = (
        Payment.objects.select_related("invoice", "invoice__order")
        .filter(invoice__in=inv_qs)
        .order_by("-created_at", "-id")[:200]
    )
    return render(
        request,
        "portal/payment_list.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "payments": payments},
    )


@portal_login_required(permission="view_reports")
def portal_reports(request: HttpRequest):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})

    if portal_perms.get("view_invoices", True) is False:
        messages.error(request, "Invoice access is disabled for this portal account.")
        if portal_user.role == PortalUser.Role.SUPPLIER:
            return redirect("portal:supplier_dashboard")
        return redirect("portal:customer_dashboard")

    party = portal_user.party
    owner = portal_user.owner
    order_type = "purchase" if portal_user.role == PortalUser.Role.SUPPLIER else "sale"

    invoices = (
        Invoice.objects.select_related("order")
        .filter(order__owner=owner, order__party=party, order__order_type__iexact=order_type)
        .order_by("-created_at", "-id")[:100]
    )
    return render(
        request,
        "portal/reports.html",
        {"portal_user": portal_user, "portal_perms": portal_perms, "invoices": invoices},
    )


@portal_login_required(permission="view_reports")
def portal_invoice_pdf(request: HttpRequest, invoice_id: int):
    portal_user: PortalUser = request.portal_user  # type: ignore[attr-defined]
    portal_perms = getattr(request, "portal_perms", {})

    if portal_perms.get("view_invoices", True) is False:
        messages.error(request, "Invoice access is disabled for this portal account.")
        if portal_user.role == PortalUser.Role.SUPPLIER:
            return redirect("portal:supplier_dashboard")
        return redirect("portal:customer_dashboard")

    party = portal_user.party
    owner = portal_user.owner
    order_type = "purchase" if portal_user.role == PortalUser.Role.SUPPLIER else "sale"

    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "order__party"),
        id=invoice_id,
        order__owner=owner,
        order__party=party,
        order__order_type__iexact=order_type,
    )
    order = invoice.order
    items = order.items.select_related("product").all().order_by("id")

    subtotal = order.subtotal_amount()
    discount = order.discount_amount or Decimal("0.00")
    sundry = order.bill_sundry_total()
    tax = order.tax_amount or Decimal("0.00")
    total = order.total_amount()

    is_gst = (invoice.gst_type or "").upper() == "GST" and (order.tax_percent or Decimal("0.00")) > 0
    cgst = sgst = igst = Decimal("0.00")
    if is_gst:
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"))
        sgst = tax - cgst

    context = {
        "invoice": invoice,
        "order": order,
        "party": order.party,
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "sundry": sundry,
        "tax": tax,
        "total": total,
        "is_gst": is_gst,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "hide_sidebar": True,
        "hide_actions": True,
    }
    pdf_bytes = render_to_pdf_bytes("commerce/invoice_print.html", context, request=request)
    if not pdf_bytes:
        return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

    filename = f"invoice_{invoice.number or invoice.id}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def secrets_token() -> str:
    import secrets

    return secrets.token_hex(32)


@require_http_methods(["GET", "POST"])
def payment_link_view(request: HttpRequest, token: str):
    link = get_object_or_404(PaymentLink.objects.select_related("invoice", "invoice__order", "invoice__order__party"), token=token)

    # Expiry handling
    try:
        if link.expires_at and timezone.now() > link.expires_at and link.status not in {PaymentLink.Status.PAID, PaymentLink.Status.EXPIRED}:
            link.status = PaymentLink.Status.EXPIRED
            link.save(update_fields=["status"])
    except Exception:
        pass

    # Mark opened
    if link.status == PaymentLink.Status.CREATED:
        link.status = PaymentLink.Status.OPENED
        link.save(update_fields=["status"])

    invoice = link.invoice
    order = invoice.order
    party = order.party
    items = order.items.select_related("product").all().order_by("id")
    payments = invoice.payments.all().order_by("-created_at", "-id")
    paid_total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    balance = (invoice.amount or Decimal("0.00")) - paid_total

    # Confirm payment (manual / gateway callback simulation)
    if request.method == "POST":
        if link.status in {PaymentLink.Status.EXPIRED, PaymentLink.Status.PAID}:
            messages.error(request, "This payment link is not payable.")
            return redirect(request.path)

        ref = (request.POST.get("reference") or "").strip()
        amount = _to_decimal(request.POST.get("amount") or link.amount or invoice.amount or 0)
        if amount <= 0:
            amount = link.amount or invoice.amount or Decimal("0.00")
        if balance <= 0:
            messages.info(request, "Invoice is already paid.")
            return redirect(request.path)
        if amount > balance:
            amount = balance

        with transaction.atomic():
            Payment.objects.create(invoice=invoice, amount=amount, method="Online", reference=ref, note="Paid via Payment Link")
            payments = invoice.payments.all()
            paid_total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            fully_paid = paid_total >= (invoice.amount or Decimal("0.00"))
            if fully_paid:
                Invoice.objects.filter(id=invoice.id).update(status="paid")
                try:
                    Order.objects.filter(id=order.id, status="pending").update(status="accepted")
                except Exception:
                    pass

            link.status = PaymentLink.Status.PAID if fully_paid else PaymentLink.Status.OPENED
            link.paid_at = timezone.now() if fully_paid else link.paid_at
            link.reference = ref[:120]
            link.save(update_fields=["status", "paid_at", "reference"])

        messages.success(request, "Payment recorded successfully.")
        return redirect(request.path)

    return render(
        request,
        "portal/payment_link.html",
        {"link": link, "invoice": invoice, "order": order, "party": party, "items": items, "paid_total": paid_total, "balance": balance, "upi_link": invoice.payment_link or ""},
    )


@require_http_methods(["GET"])
def payment_link_invoice_pdf(request: HttpRequest, token: str):
    """
    Public invoice PDF download for a PaymentLink token.

    This is used for sharing invoice PDFs over WhatsApp/SMS without requiring portal login.
    """
    link = get_object_or_404(PaymentLink.objects.select_related("invoice", "invoice__order", "invoice__order__party"), token=token)
    invoice = link.invoice
    order = invoice.order
    items = order.items.select_related("product").all().order_by("id")

    subtotal = order.subtotal_amount()
    discount = order.discount_amount or Decimal("0.00")
    sundry = order.bill_sundry_total()
    tax = order.tax_amount or Decimal("0.00")
    total = order.total_amount()

    is_gst = (invoice.gst_type or "").upper() == "GST" and (order.tax_percent or Decimal("0.00")) > 0
    cgst = sgst = igst = Decimal("0.00")
    if is_gst:
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"))
        sgst = tax - cgst

    context = {
        "invoice": invoice,
        "order": order,
        "party": order.party,
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "sundry": sundry,
        "tax": tax,
        "total": total,
        "is_gst": is_gst,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "hide_sidebar": True,
        "hide_actions": True,
    }
    pdf_bytes = render_to_pdf_bytes("commerce/invoice_print.html", context, request=request)
    if not pdf_bytes:
        return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

    filename = f"invoice_{invoice.number or invoice.id}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# -------------------- Portal API --------------------

@csrf_exempt
@require_POST
def api_portal_login(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    role = str(payload.get("role") or "").strip().lower()
    if role not in {PortalUser.Role.CUSTOMER, PortalUser.Role.SUPPLIER}:
        role = PortalUser.Role.CUSTOMER

    try:
        if not portal_enabled():
            return JsonResponse({"ok": False, "error": "Portal is disabled"}, status=403)
        if role == PortalUser.Role.CUSTOMER and not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
        if role == PortalUser.Role.SUPPLIER and not supplier_portal_enabled():
            return JsonResponse({"ok": False, "error": "Supplier portal is disabled"}, status=403)
    except Exception:
        pass

    if not username or not password:
        return JsonResponse({"ok": False, "error": "Missing username/password"}, status=400)

    pu = PortalUser.objects.select_related("party", "owner").filter(username__iexact=username, role=role).first()
    if not pu or not pu.is_active:
        return JsonResponse({"ok": False, "error": "Invalid credentials"}, status=401)
    if not pu.check_password(password):
        return JsonResponse({"ok": False, "error": "Invalid credentials"}, status=401)

    token = pu.issue_api_token(rotate=True)
    pu.api_token_last_used_at = timezone.now()
    pu.save(update_fields=["api_token_last_used_at"])
    return JsonResponse(
        {
            "ok": True,
            "token": token,
            "role": pu.role,
            "must_change_password": bool(getattr(pu, "must_change_password", False)),
            "party": {"id": pu.party_id, "name": pu.party.name},
        }
    )


def _portal_user_for_api(request: HttpRequest) -> PortalUser | None:
    return get_portal_user_from_session(request) or get_portal_user_from_token(request)


def _api_perm_allowed(portal_user: PortalUser, key: str) -> bool:
    try:
        for p in portal_user.permissions.all():
            if str(p.key) == key:
                return bool(p.allowed)
    except Exception:
        pass
    return True


@csrf_exempt
@require_POST
def api_cart_add(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    if pu.role != PortalUser.Role.CUSTOMER:
        return JsonResponse({"ok": False, "error": "Only customers can order"}, status=403)
    try:
        if not portal_enabled() or not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}
    product_id = payload.get("product_id")
    qty = int(payload.get("qty") or 1)
    qty = max(qty, 1)

    product = Product.objects.filter(id=product_id, owner=pu.owner).first()
    if not product:
        return JsonResponse({"ok": False, "error": "Product not found"}, status=404)

    available = int(getattr(product, "stock", 0) or 0)
    if available <= 0:
        return JsonResponse({"ok": False, "error": "Out of stock"}, status=400)
    if qty > available:
        qty = available

    obj, _ = CartItem.objects.get_or_create(portal_user=pu, product=product, defaults={"qty": qty})
    if obj.qty != qty:
        obj.qty = qty
        obj.save(update_fields=["qty", "updated_at"])

    total_qty = CartItem.objects.filter(portal_user=pu).aggregate(c=Sum("qty")).get("c") or 0
    return JsonResponse({"ok": True, "cart_qty": total_qty, "qty": int(obj.qty or 0), "stock": available})


@csrf_exempt
@require_POST
def api_cart_update(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    if pu.role != PortalUser.Role.CUSTOMER:
        return JsonResponse({"ok": False, "error": "Only customers can order"}, status=403)
    try:
        if not portal_enabled() or not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    items = payload.get("items") or []
    if not isinstance(items, list):
        return JsonResponse({"ok": False, "error": "items must be a list"}, status=400)

    updated = 0
    removed = 0
    clamped = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        pid = it.get("product_id")
        qty = int(it.get("qty") or 0)
        ci = CartItem.objects.filter(portal_user=pu, product_id=pid).first()
        if not ci:
            continue
        if qty <= 0:
            ci.delete()
            removed += 1
        else:
            available = int(getattr(ci.product, "stock", 0) or 0)
            if available <= 0:
                ci.delete()
                removed += 1
                continue
            if qty > available:
                qty = available
                clamped += 1
            if ci.qty != qty:
                ci.qty = qty
                ci.save(update_fields=["qty", "updated_at"])
                updated += 1

    total_qty = CartItem.objects.filter(portal_user=pu).aggregate(c=Sum("qty")).get("c") or 0
    return JsonResponse({"ok": True, "updated": updated, "removed": removed, "clamped": clamped, "cart_qty": total_qty})


@csrf_exempt
@require_POST
def api_cart_clear(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        if pu.role == PortalUser.Role.CUSTOMER and (not portal_enabled() or not customer_portal_enabled()):
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
        if pu.role == PortalUser.Role.SUPPLIER and (not portal_enabled() or not supplier_portal_enabled()):
            return JsonResponse({"ok": False, "error": "Supplier portal is disabled"}, status=403)
    except Exception:
        pass
    if pu.role == PortalUser.Role.CUSTOMER and not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
    CartItem.objects.filter(portal_user=pu).delete()
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def api_products(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    if pu.role != PortalUser.Role.CUSTOMER:
        return JsonResponse({"ok": False, "error": "Only customers can browse products"}, status=403)
    try:
        if not portal_enabled() or not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    q = str(request.GET.get("q") or "").strip()
    qs = Product.objects.filter(owner=pu.owner).order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)

    products = []
    for p in qs[:200]:
        image_url = ""
        try:
            if getattr(p, "image", None):
                image_url = request.build_absolute_uri(p.image.url)
        except Exception:
            image_url = ""
        products.append(
            {
                "id": p.id,
                "name": p.name,
                "sku": getattr(p, "sku", "") or "",
                "price": str(getattr(p, "price", "0") or "0"),
                "stock": int(getattr(p, "stock", 0) or 0),
                "unit": getattr(p, "unit", "") or "",
                "gst_rate": str(getattr(p, "gst_rate", "0") or "0"),
                "description": getattr(p, "description", "") or "",
                "image_url": image_url,
            }
        )
    return JsonResponse({"ok": True, "products": products})


@require_http_methods(["GET"])
def api_cart_get(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    if pu.role != PortalUser.Role.CUSTOMER:
        return JsonResponse({"ok": False, "error": "Only customers can order"}, status=403)
    try:
        if not portal_enabled() or not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    items = (
        CartItem.objects.filter(portal_user=pu)
        .select_related("product")
        .order_by("id")
    )
    rows = []
    subtotal = Decimal("0.00")
    total_qty = 0
    for it in items:
        prod = it.product
        qty = int(it.qty or 0)
        price = _to_decimal(getattr(prod, "price", 0))
        line_total = price * Decimal(qty)
        subtotal += line_total
        total_qty += qty
        rows.append(
            {
                "product_id": prod.id,
                "name": prod.name,
                "price": str(price),
                "qty": qty,
                "line_total": str(line_total),
                "stock": int(getattr(prod, "stock", 0) or 0),
            }
        )
    return JsonResponse({"ok": True, "items": rows, "subtotal": str(subtotal), "cart_qty": total_qty})


@csrf_exempt
@require_POST
def api_checkout(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    if pu.role != PortalUser.Role.CUSTOMER:
        return JsonResponse({"ok": False, "error": "Only customers can checkout"}, status=403)
    try:
        if not portal_enabled() or not customer_portal_enabled():
            return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "place_orders"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    cart_items = list(CartItem.objects.filter(portal_user=pu).select_related("product"))
    if not cart_items:
        return JsonResponse({"ok": False, "error": "Cart is empty"}, status=400)

    stock_issues = []
    for it in cart_items:
        prod = getattr(it, "product", None)
        if not prod:
            continue
        available = int(getattr(prod, "stock", 0) or 0)
        desired = int(it.qty or 0)
        if available <= 0:
            stock_issues.append(f"{getattr(prod, 'name', 'Item')} is out of stock.")
        elif desired > available:
            stock_issues.append(f"{getattr(prod, 'name', 'Item')}: only {available} available (requested {desired}).")
    if stock_issues:
        return JsonResponse({"ok": False, "error": "Insufficient stock", "details": stock_issues}, status=400)

    with transaction.atomic():
        order = Order.objects.create(
            owner=pu.owner,
            party=pu.party,
            order_type="SALE",
            status="pending",
            notes="Placed via Customer Portal API",
            order_source="Customer Portal",
        )
        for it in cart_items:
            qty = int(it.qty or 0)
            if qty <= 0:
                continue
            OrderItem.objects.create(order=order, product=it.product, qty=qty, price=getattr(it.product, "price", 0) or 0)
        order.save()
        PortalOrder.objects.create(
            owner=pu.owner,
            portal_user=pu,
            party=pu.party,
            commerce_order=order,
            status=PortalOrder.Status.SUBMITTED,
            total_amount=order.total_amount(),
            payload={"source": "customer_portal_api"},
        )
        CartItem.objects.filter(portal_user=pu).delete()

    return JsonResponse({"ok": True, "order_id": order.id})


@require_http_methods(["GET"])
def api_orders(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        if not portal_enabled():
            return JsonResponse({"ok": False, "error": "Portal is disabled"}, status=403)
    except Exception:
        pass

    if pu.role == PortalUser.Role.SUPPLIER:
        if not _api_perm_allowed(pu, "view_purchase_history"):
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
        order_type = "PURCHASE"
    else:
        if not _api_perm_allowed(pu, "place_orders"):
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
        order_type = "SALE"

    qs = (
        Order.objects.filter(owner=pu.owner, party=pu.party, order_type__iexact=order_type)
        .annotate(
            total=Sum(
                F("items__qty") * F("items__price"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .order_by("-created_at", "-id")[:100]
    )
    data = []
    for o in qs:
        data.append(
            {
                "id": o.id,
                "status": o.status,
                "order_type": o.order_type,
                "created_at": o.created_at.isoformat() if getattr(o, "created_at", None) else "",
                "total": str(getattr(o, "total", "") or "0.00"),
            }
        )
    return JsonResponse({"ok": True, "orders": data})


@require_http_methods(["GET"])
def api_invoices(request: HttpRequest):
    pu = _portal_user_for_api(request)
    if not pu:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        if not portal_enabled():
            return JsonResponse({"ok": False, "error": "Portal is disabled"}, status=403)
    except Exception:
        pass
    if not _api_perm_allowed(pu, "view_invoices"):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    order_type = "purchase" if pu.role == PortalUser.Role.SUPPLIER else "sale"
    qs = (
        Invoice.objects.select_related("order")
        .filter(order__owner=pu.owner, order__party=pu.party, order__order_type__iexact=order_type)
        .order_by("-created_at", "-id")[:100]
    )
    invoices = []
    for inv in qs:
        invoices.append(
            {
                "id": inv.id,
                "number": inv.number,
                "status": inv.status,
                "amount": str(inv.amount or "0.00"),
                "created_at": inv.created_at.isoformat() if getattr(inv, "created_at", None) else "",
                "order_id": getattr(inv.order, "id", None),
            }
        )
    return JsonResponse({"ok": True, "invoices": invoices})


# -------------------- ERP-side management --------------------

@login_required
def manage_customers(request: HttpRequest):
    return _manage_list(request, party_type="customer", page_title="Customer Portal")


@login_required
def manage_suppliers(request: HttpRequest):
    return _manage_list(request, party_type="supplier", page_title="Supplier Portal")


def _manage_list(request: HttpRequest, *, party_type: str, page_title: str):
    if not can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot manage portal access.")
        return redirect("accounts:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = Party.objects.filter(party_type=party_type)
    if not (request.user.is_staff or request.user.is_superuser):
        qs = qs.filter(owner=request.user)
    if q:
        qs = qs.filter(name__icontains=q)

    parties = qs.select_related("owner", "portal_account").order_by("-created_at", "-id")[:200]
    portal_map = {p.id: getattr(p, "portal_account", None) for p in parties}
    portal_globally_enabled = True
    portal_role_enabled = True
    try:
        portal_globally_enabled = bool(portal_enabled())
        portal_role_enabled = bool(customer_portal_enabled() if party_type == "customer" else supplier_portal_enabled())
    except Exception:
        portal_globally_enabled = True
        portal_role_enabled = True
    return render(
        request,
        "portal/manage_list.html",
        {
            "page_title": page_title,
            "party_type": party_type,
            "q": q,
            "parties": parties,
            "portal_map": portal_map,
            "portal_globally_enabled": portal_globally_enabled,
            "portal_role_enabled": portal_role_enabled,
        },
    )


@login_required
def manage_party_portal(request: HttpRequest, party_id: int):
    party = get_object_or_404(Party.objects.select_related("owner"), id=party_id)
    if not can_edit(request.user):
        messages.error(request, "Permission denied.")
        return redirect("accounts:dashboard")
    if not (request.user.is_staff or request.user.is_superuser) and party.owner_id != request.user.id:
        messages.error(request, "Permission denied.")
        return redirect("accounts:dashboard")

    desired_role = PortalUser.Role.SUPPLIER if (party.party_type or "").lower() == "supplier" else PortalUser.Role.CUSTOMER
    portal_globally_enabled = True
    portal_role_enabled = True
    try:
        portal_globally_enabled = bool(portal_enabled())
        portal_role_enabled = bool(customer_portal_enabled() if desired_role == PortalUser.Role.CUSTOMER else supplier_portal_enabled())
    except Exception:
        portal_globally_enabled = True
        portal_role_enabled = True

    portal_user = (
        PortalUser.objects.filter(party=party)
        .select_related("party", "owner")
        .prefetch_related("permissions")
        .first()
    )

    effective_role = portal_user.role if portal_user else desired_role
    perm_keys = list(DEFAULT_PERMISSION_KEYS.get(effective_role, []))
    perm_map: dict[str, bool] = {}
    if portal_user:
        try:
            perm_map = {str(p.key): bool(p.allowed) for p in portal_user.permissions.all()}
        except Exception:
            perm_map = {}

    new_password = ""
    try:
        if request.session.get("portal_temp_party_id") == party.id:
            new_password = str(request.session.get("portal_temp_password") or "")
            request.session.pop("portal_temp_party_id", None)
            request.session.pop("portal_temp_password", None)
    except Exception:
        new_password = ""

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action in {"create", "reset_password", "send_welcome"}:
            if not portal_globally_enabled or not portal_role_enabled:
                messages.error(request, "Portal is disabled in Settings.")
                return redirect(request.path)
            res = create_portal_account_for_party(party, created_by=request.user, rotate_password=(action != "create"))
            portal_user = res.portal_user if res else portal_user
            new_password = (res.plain_password if res else "") or ""
            if portal_user:
                if action == "create":
                    messages.success(request, "Portal access created.")
                else:
                    messages.success(request, "Password reset + Welcome kit sent (best-effort).")
            if new_password:
                try:
                    request.session["portal_temp_party_id"] = party.id
                    request.session["portal_temp_password"] = new_password
                except Exception:
                    pass
        elif action == "set_password" and portal_user:
            if not portal_globally_enabled or not portal_role_enabled:
                messages.error(request, "Portal is disabled in Settings.")
                return redirect(request.path)
            pw1 = str(request.POST.get("new_password") or "")
            pw2 = str(request.POST.get("confirm_password") or "")
            if len(pw1) < 8:
                messages.error(request, "Password must be at least 8 characters.")
                return redirect(request.path)
            if pw1 != pw2:
                messages.error(request, "Password confirmation does not match.")
                return redirect(request.path)
            portal_user.set_password(pw1)
            portal_user.must_change_password = True
            portal_user.save(update_fields=["password_hash", "must_change_password", "updated_at"])
            try:
                from portal.services import send_welcome_kit

                link = f"{portal_base_url()}/accounts/login/?role={portal_user.role}"
                send_welcome_kit(portal_user=portal_user, plain_password=pw1, login_link=link)
            except Exception:
                logger.exception("Failed to send welcome kit after manual password set")
            try:
                request.session["portal_temp_party_id"] = party.id
                request.session["portal_temp_password"] = pw1
            except Exception:
                pass
            messages.success(request, "Password updated and Welcome Kit sent (best-effort).")
        elif action == "update_permissions" and portal_user:
            selected = set(request.POST.getlist("perm") or [])
            for k in perm_keys:
                allowed = k in selected
                PortalPermission.objects.update_or_create(
                    portal_user=portal_user,
                    key=k,
                    defaults={"allowed": bool(allowed)},
                )
            messages.success(request, "Portal permissions updated.")
        elif action == "disable" and portal_user:
            portal_user.is_active = False
            portal_user.save(update_fields=["is_active"])
            messages.success(request, "Portal access disabled.")
        elif action == "enable" and portal_user:
            portal_user.is_active = True
            portal_user.save(update_fields=["is_active"])
            messages.success(request, "Portal access enabled.")
        elif action == "delete" and portal_user:
            portal_user.delete()
            portal_user = None
            messages.success(request, "Portal access deleted.")
        elif action == "update_username" and portal_user:
            new_username = (request.POST.get("username") or "").strip()
            if not new_username:
                messages.error(request, "Username cannot be empty.")
            elif PortalUser.objects.filter(username__iexact=new_username).exclude(id=portal_user.id).exists():
                messages.error(request, "Username is already taken.")
            else:
                portal_user.username = new_username[:80]
                portal_user.save(update_fields=["username"])
                messages.success(request, "Username updated.")

        return redirect(request.path)

    login_url = f"{portal_base_url()}/accounts/login/?role={effective_role}"
    after_login_urls: dict[str, str] = {}
    try:
        if effective_role == PortalUser.Role.CUSTOMER:
            after_login_urls = {
                "ecommerce": f"{portal_base_url()}{reverse('portal:customer_ecommerce_dashboard')}",
                "billing": f"{portal_base_url()}{reverse('portal:customer_billing_dashboard')}",
            }
        else:
            after_login_urls = {"dashboard": f"{portal_base_url()}{reverse('portal:supplier_dashboard')}"}
    except Exception:
        after_login_urls = {}
    return render(
        request,
        "portal/manage_party.html",
        {
            "party": party,
            "portal_user": portal_user,
            "login_url": login_url,
            "after_login_urls": after_login_urls,
            "new_password": new_password,
            "portal_globally_enabled": portal_globally_enabled,
            "portal_role_enabled": portal_role_enabled,
            "perm_keys": perm_keys,
            "perm_items": [{"key": k, "label": str(k).replace("_", " ").title()} for k in perm_keys],
            "perm_map": perm_map,
        },
    )
