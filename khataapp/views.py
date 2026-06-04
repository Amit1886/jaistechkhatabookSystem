from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Case, When, Value, DecimalField, F
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.contrib.admin.views.decorators import staff_member_required

from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from accounts.roles import can_delete as erp_can_delete, can_edit as erp_can_edit

from khataapp.models import Party, SupplierPayment, Transaction
from commerce.models import Order
from khataapp.forms import SupplierPaymentForm
from khataapp.services.supplier_services import SupplierService

from billing.services import user_has_feature
from .models import ContactMessage, FieldAgent, LoginLink, OfflineMessage
from .forms import FieldAgentForm
from .forms import PartyForm


@login_required
def profile_view(request):
    return render(request, "khataapp/profile.html")


@login_required
def update_plan(request):
    return HttpResponse("update_plan working")

@login_required
def my_credits(request):
    return HttpResponse("my_credits working")


@login_required
def add_transaction(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add transactions.")
        return redirect("khataapp:transaction_list")

    parties = Party.objects.filter(owner=request.user).order_by("name")

    if request.method == "POST":
        party_id = request.POST.get("party")
        txn_type = request.POST.get("txn_type")
        txn_mode = request.POST.get("txn_mode") or "cash"
        notes = request.POST.get("notes") or ""
        receipt = request.FILES.get("receipt")
        gst_type = request.POST.get("gst_type") or None

        amount_raw = request.POST.get("amount") or ""
        date_raw = request.POST.get("date") or ""

        if not party_id or not txn_type or not amount_raw:
            messages.error(request, "Please fill Party, Type and Amount.")
            return render(request, "khataapp/add_transaction.html", {"parties": parties})

        party = Party.objects.filter(id=party_id, owner=request.user).first()
        if not party:
            messages.error(request, "Invalid party selected.")
            return render(request, "khataapp/add_transaction.html", {"parties": parties})

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError):
            messages.error(request, "Invalid amount.")
            return render(request, "khataapp/add_transaction.html", {"parties": parties})

        txn_date = timezone.now().date()
        if date_raw:
            try:
                txn_date = datetime.fromisoformat(date_raw).date()
            except ValueError:
                pass

        Transaction.objects.create(
            party=party,
            txn_type=txn_type,
            txn_mode=txn_mode,
            amount=amount,
            date=txn_date,
            notes=notes,
            receipt=receipt,
            gst_type=gst_type,
            voucher_type="manual",
            created_by=request.user,
        )
        messages.success(request, "✅ Transaction saved.")
        return redirect("khataapp:transaction_list")

    return render(request, "khataapp/add_transaction.html", {"parties": parties})

@login_required
def transaction_list(request):
    q = (request.GET.get("q") or "").strip()
    txn_type = (request.GET.get("type") or "").strip().lower()
    txn_mode = (request.GET.get("mode") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Transaction.objects.select_related("party").filter(party__owner=request.user, is_deleted=False)
    if q:
        qs = qs.filter(Q(party__name__icontains=q) | Q(notes__icontains=q) | Q(amount__icontains=q))
    if txn_type in {"credit", "debit"}:
        qs = qs.filter(txn_type=txn_type)
    if txn_mode:
        qs = qs.filter(txn_mode=txn_mode)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    qs = qs.order_by("-date", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "transactions": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "type": txn_type,
        "mode": txn_mode,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("khataapp/partials/transaction_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "khataapp/transaction_list.html", context)

@login_required
def transaction_edit(request, id):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit transactions.")
        return redirect("khataapp:transaction_list")

    txn = get_object_or_404(Transaction, id=id, party__owner=request.user, is_deleted=False)
    parties = Party.objects.filter(owner=request.user).order_by("name")

    if request.method == "POST":
        party_id = request.POST.get("party")
        txn_type = request.POST.get("txn_type")
        amount_raw = request.POST.get("amount") or ""
        date_raw = request.POST.get("date") or ""
        notes = request.POST.get("notes") or ""

        party = Party.objects.filter(id=party_id, owner=request.user).first()
        if not party:
            messages.error(request, "Invalid party selected.")
            return render(request, "khataapp/transaction_edit.html", {"txn": txn, "parties": parties})

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError):
            messages.error(request, "Invalid amount.")
            return render(request, "khataapp/transaction_edit.html", {"txn": txn, "parties": parties})

        txn_date = txn.date
        if date_raw:
            try:
                txn_date = datetime.fromisoformat(date_raw).date()
            except ValueError:
                pass

        txn.party = party
        txn.txn_type = txn_type
        txn.amount = amount
        txn.date = txn_date
        txn.notes = notes
        txn.save(update_fields=["party", "txn_type", "amount", "date", "notes"])
        messages.success(request, "✅ Transaction updated.")
        return redirect("khataapp:transaction_view", id=txn.id)

    return render(request, "khataapp/transaction_edit.html", {"txn": txn, "parties": parties})

@login_required
def transaction_view(request, id):
    txn = get_object_or_404(Transaction.objects.select_related("party"), id=id, party__owner=request.user, is_deleted=False)
    return render(request, "khataapp/transaction_view.html", {"txn": txn})

@login_required
def transaction_delete(request, id):
    if request.method != "POST":
        return HttpResponse(status=405)

    txn = get_object_or_404(Transaction, id=id, party__owner=request.user, is_deleted=False)
    txn.is_deleted = True
    txn.deleted_at = timezone.now()
    txn.save(update_fields=["is_deleted", "deleted_at"])
    messages.success(request, "✅ Transaction deleted.")
    return redirect("khataapp:transaction_list")

@login_required
def add_party(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add parties.")
        return redirect("khataapp:party_list")

    if request.method == "POST":
        form = PartyForm(request.POST)
        if form.is_valid():
            party = form.save(commit=False)
            party.owner = request.user
            party.save()
            return redirect("khataapp:party_list")
    else:
        form = PartyForm()

    return render(request, "khataapp/add_party.html", {"form": form})

@login_required
def party_list(request):
    q = (request.GET.get("q") or "").strip()
    party_type = (request.GET.get("type") or "").strip().lower()
    status = (request.GET.get("status") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Party.objects.filter(owner=request.user)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(mobile__icontains=q) | Q(email__icontains=q))
    if party_type in {"customer", "supplier"}:
        qs = qs.filter(party_type=party_type)
    if status == "accepted":
        qs = qs.filter(is_active=True)
    elif status == "rejected":
        qs = qs.filter(is_active=False)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.annotate(
        credit_total=Sum(
            Case(
                When(transactions__txn_type="credit", then=F("transactions__amount")),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
        debit_total=Sum(
            Case(
                When(transactions__txn_type="debit", then=F("transactions__amount")),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
    ).annotate(balance_amount=F("credit_total") - F("debit_total")).order_by("-created_at", "-id")

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "parties": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "type": party_type,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("khataapp/partials/party_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "khataapp/party_list.html", context)

@login_required
def party_view(request, party_id):
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can delete.")
        return redirect("khataapp:party_list")

    party = get_object_or_404(Party, id=party_id, owner=request.user)
    txns = party.transactions.all().order_by("-date", "-id")[:50]

    smart_khata = None
    if (party.party_type or "").lower() == "customer":
        try:
            from smart_khata.models import PaymentBehavior
            from smart_khata.services.credit_score import credit_score_level, get_invoice_due_date, update_party_credit_metrics
            from commerce.models import Invoice
            from khataapp.models import ReminderLog

            score_res = update_party_credit_metrics(party)
            behaviors = (
                PaymentBehavior.objects.select_related("invoice")
                .filter(owner=request.user, customer=party)
                .order_by("-created_at", "-id")[:20]
            )
            reminders = (
                ReminderLog.objects.select_related("invoice")
                .filter(party=party, reminder_type="due")
                .order_by("-created_at", "-id")[:20]
            )

            # Outstanding invoices (SALE)
            invoices = (
                Invoice.objects.select_related("order")
                .prefetch_related("payments")
                .filter(order__owner=request.user, order__party=party, order__order_type__iexact="sale")
                .exclude(status__iexact="cancelled")
                .order_by("-created_at", "-id")[:20]
            )
            today = timezone.localdate()
            outstanding_invoices = []
            for inv in invoices:
                try:
                    paid = sum((p.amount or Decimal("0.00")) for p in inv.payments.all() if not getattr(p, "is_deleted", False))
                except Exception:
                    paid = Decimal("0.00")
                outstanding = (inv.amount or Decimal("0.00")) - paid
                if outstanding <= 0:
                    continue
                due_dt = get_invoice_due_date(inv)
                outstanding_invoices.append(
                    {
                        "invoice": inv,
                        "outstanding": outstanding,
                        "due_date": due_dt,
                        "days_overdue": (today - due_dt).days,
                    }
                )

            smart_khata = {
                "score": int(score_res.score),
                "level": score_res.level,
                "badge": credit_score_level(int(score_res.score)),
                "total_due": score_res.total_due,
                "average_delay": int(score_res.average_delay_days),
                "last_payment_date": score_res.last_payment_date,
                "behaviors": behaviors,
                "reminders": reminders,
                "outstanding_invoices": outstanding_invoices,
            }
        except Exception:
            smart_khata = None

    context = {
        "party": party,
        "transactions": txns,
        "smart_khata": smart_khata,
    }
    return render(request, "khataapp/party_view.html", context)

@login_required
def edit_party(request, party_id):
    party = get_object_or_404(Party, id=party_id, owner=request.user)

    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit parties.")
        return redirect("khataapp:party_view", party_id=party.id)

    if request.method == "POST":
        form = PartyForm(request.POST, instance=party)
        if form.is_valid():
            form.save()
            messages.success(request, "Party updated successfully")
            return redirect("khataapp:party_list")
    else:
        form = PartyForm(instance=party)

    return render(request, "khataapp/add_party.html", {
        "form": form,
        "party": party
    })

@login_required
def delete_party(request, party_id):
    if request.method != "POST":
        return HttpResponse(status=405)

    party = get_object_or_404(Party, id=party_id, owner=request.user)
    party.delete()
    messages.success(request, "Party deleted")
    return redirect("khataapp:party_list")

@login_required
def credit_report_view(request):
    parties = Party.objects.filter(owner=request.user)
    return render(request, "khataapp/credit_report.html", {
        "parties": parties
    })

# ---------------- Supplier Management Views ----------------
@login_required
def supplier_dashboard(request):
    """Supplier purchase and due management dashboard"""
    suppliers = SupplierService.get_supplier_summary(request.user)
    summary = SupplierService.get_dashboard_summary(request.user)
    alerts = SupplierService.get_payment_alerts(request.user)

    context = {
        'suppliers': suppliers,
        'summary': summary,
        'alerts': alerts,
    }
    return render(request, 'khataapp/supplier_dashboard.html', context)


@login_required
def supplier_detail(request, supplier_id):
    """Detailed view of a supplier's transactions and outstanding amounts"""
    supplier = get_object_or_404(Party, id=supplier_id, owner=request.user, party_type='supplier')

    # Get outstanding orders
    outstanding_orders = Order.objects.filter(
        party=supplier,
        order_type='PURCHASE',
        due_amount__gt=0
    ).order_by('payment_due_date')

    # Get payment history
    payments = SupplierPayment.objects.filter(
        supplier=supplier
    ).select_related('order').order_by('-payment_date')

    # Get supplier summary
    suppliers_data = SupplierService.get_supplier_summary(request.user)
    summary = next((s for s in suppliers_data if s['id'] == supplier.id), {})

    # Get ledger
    ledger = SupplierService.get_supplier_ledger(supplier)

    context = {
        'supplier': supplier,
        'outstanding_orders': outstanding_orders,
        'payments': payments,
        'summary': summary,
        'ledger': ledger,
        'today': timezone.now().date(),
        'due_soon_date': timezone.now().date() + timedelta(days=7),
    }
    return render(request, 'khataapp/supplier_detail.html', context)


@login_required
def add_supplier_payment(request):
    """Add payment to supplier for outstanding purchase"""
    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.cleaned_data['order']
            payment = SupplierService.process_supplier_payment(
                order=order,
                amount=form.cleaned_data['amount'],
                payment_mode=form.cleaned_data['payment_mode'],
                reference=form.cleaned_data.get('reference'),
                notes=form.cleaned_data.get('notes'),
                payment_date=form.cleaned_data.get('payment_date')
            )

            messages.success(request, f"Payment of ₹{payment.amount} added successfully!")
            return redirect('khataapp:supplier_detail', supplier_id=order.party.id)
    else:
        form = SupplierPaymentForm(user=request.user)

        # Pre-select supplier if provided in query params
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            try:
                supplier = Party.objects.get(id=supplier_id, owner=request.user, party_type='supplier')
                # Filter orders for this supplier
                form.fields['order'].queryset = Order.objects.filter(
                    party=supplier,
                    order_type='PURCHASE',
                    due_amount__gt=0
                )
            except Party.DoesNotExist:
                pass

        # Pre-select order if provided in query params
        order_id = request.GET.get('order')
        if order_id:
            try:
                order = Order.objects.get(id=order_id, owner=request.user, order_type='PURCHASE')
                form.initial['order'] = order
            except Order.DoesNotExist:
                pass
                return render(request, 'khataapp/add_supplier_payment.html', {'form': form})


@csrf_exempt
def submit_contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        mobile = request.POST.get("mobile")
        email = request.POST.get("email")
        message_text = request.POST.get("message")

        if not name or not mobile or not email or not message_text:
            return JsonResponse({"status": "error", "message": "Missing fields"})

        ContactMessage.objects.create(
            name=name,
            mobile=mobile,
            email=email,
            message=message_text
        )

        return JsonResponse({
            "status": "success",
            "message": "Your message has been received successfully."
        })

    return JsonResponse({"status": "error", "message": "Invalid request"})


@staff_member_required
def admin_contact_leads_count(request):
    unread = ContactMessage.objects.filter(forwarded_to_admin=False).count()
    total = ContactMessage.objects.count()
    return JsonResponse({
        "unread": unread,
        "total": total,
    })

# ---------------- Field Agent Management ----------------
def _owner_agent_access(request):
    # Use ERP roles instead of Django staff only (supports admin users who aren't `is_staff`).
    try:
        from accounts.roles import can_delete as erp_can_delete

        if not erp_can_delete(request.user):
            return False
    except Exception:
        if not (request.user.is_staff or request.user.is_superuser):
            return False
    return True


AGENT_PERMISSION_TOGGLES = [
    ("billing.role.field_agent", "Field agent role"),
    ("portal.view_invoices", "View invoices"),
    ("portal.view_reports", "View reports"),
    ("portal.make_payments", "Record payments"),
    ("billing.user.view_reports", "Reports access"),
    ("billing.user.manage_locations", "Location controls"),
]

AGENT_FEATURE_GROUPS = ["Portal", "Billing", "Commerce", "Inventory", "Advanced", "Communication", "Reports"]


def _truthy_post(value):
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _perm_state(user, key, default=False):
    if not user:
        return bool(default)
    canonical = key.replace(".", "_")
    try:
        blob = getattr(user, "permissions_json", None) or {}
        if isinstance(blob, dict):
            for candidate in (key, canonical):
                if candidate in blob:
                    return blob.get(candidate) in {True, 1, "1", "true", "yes", "on"}
    except Exception:
        pass
    try:
        return bool(user.has_permission(key))
    except Exception:
        return bool(default)


def _agent_access_context(member=None):
    features = []
    try:
        from billing.models import FeatureRegistry, UserFeatureOverride
        from billing.services import user_has_feature

        features = list(
            FeatureRegistry.objects.filter(active=True, group__in=AGENT_FEATURE_GROUPS)
            .order_by("group", "sort_order", "id")[:100]
        )
        overrides = {}
        if member:
            overrides = {
                o.feature_id: o
                for o in UserFeatureOverride.objects.filter(user=member, feature__in=features).select_related("feature")
            }
    except Exception:
        UserFeatureOverride = None
        user_has_feature = None
        overrides = {}

    feature_rows = []
    for feature in features:
        override = overrides.get(feature.id)
        default_enabled = feature.key == "field.agents"
        effective = default_enabled
        if member:
            try:
                effective = bool(user_has_feature(member, feature.key)) if user_has_feature else bool(override and override.is_enabled)
            except Exception:
                effective = bool(override and override.is_enabled)
        feature_rows.append(
            {
                "id": feature.id,
                "group": feature.group,
                "label": feature.label,
                "key": feature.key,
                "effective": effective,
                "recommended": feature.key in {"field.agents", "portal.payments", "communication.whatsapp", "reports.account_summary"},
            }
        )

    return {
        "permission_toggles": [
            {"key": key, "label": label, "enabled": _perm_state(member, key, key == "billing.role.field_agent")}
            for key, label in AGENT_PERMISSION_TOGGLES
        ],
        "feature_rows": feature_rows,
        "perm_enabled_count": sum(1 for key, _label in AGENT_PERMISSION_TOGGLES if _perm_state(member, key, key == "billing.role.field_agent")),
        "perm_total_count": len(AGENT_PERMISSION_TOGGLES),
        "feature_enabled_count": sum(1 for item in feature_rows if item.get("effective")),
        "feature_total_count": len(feature_rows),
    }


def _save_agent_access_controls(request, member, role):
    if not member:
        return

    member.parent = request.user
    member.billing_role_type = "field_agent"
    member.billing_child_role = (role or "collector").strip()
    member.is_active = _truthy_post(request.POST.get("is_active"))

    blob = getattr(member, "permissions_json", None) or {}
    if not isinstance(blob, dict):
        blob = {}
    for key, _label in AGENT_PERMISSION_TOGGLES:
        enabled = _truthy_post(request.POST.get(f"perm__{key}"))
        blob[key] = enabled
        blob[key.replace(".", "_")] = enabled
    blob["feature:field.agents"] = True
    member.permissions_json = blob

    try:
        from billing.hierarchy import apply_billing_defaults_to_user

        apply_billing_defaults_to_user(member, overwrite=False)
    except Exception:
        pass

    update_fields = ["parent", "billing_role_type", "billing_child_role", "is_active", "permissions_json"]
    if hasattr(member, "mobile") and request.POST.get("mobile"):
        member.mobile = (request.POST.get("mobile") or "").strip()
        update_fields.append("mobile")
    member.save(update_fields=update_fields)

    try:
        from billing.models import FeatureRegistry, UserFeatureOverride

        features = list(FeatureRegistry.objects.filter(active=True, group__in=AGENT_FEATURE_GROUPS).only("id", "key"))
        for feature in features:
            posted = _truthy_post(request.POST.get(f"feature__{feature.id}"))
            if feature.key == "field.agents":
                posted = True
            UserFeatureOverride.objects.update_or_create(
                user=member,
                feature=feature,
                defaults={"is_enabled": posted, "note": "agent-dashboard"},
            )
    except Exception:
        pass


@login_required
def agents_home(request):
    """
    /app/agents/

    - If logged in user is a FieldAgent => send them to their dashboard (collector/staff).
    - If logged in user is an admin/owner with feature access => open agent management list.
    - Otherwise => show locked screen.
    """
    agent = getattr(request.user, "field_agent_profile", None)
    if agent and getattr(agent, "is_active", False):
        # Agent-side dashboard
        if (getattr(agent, "role", "") or "").lower() == "staff":
            return redirect("accounts:staff_dashboard")
        return redirect("accounts:collector_dashboard")

    # Admin-side management
    if _owner_agent_access(request):
        return redirect("khataapp:field_agent_list")

    return render(request, "khataapp/agent_locked.html")


@login_required
def field_agent_list(request):
    if not _owner_agent_access(request):
        return render(request, "khataapp/agent_locked.html")

    agents = FieldAgent.objects.filter(owner=request.user).select_related("user")
    return render(request, "khataapp/agent_list.html", {"agents": agents})


@login_required
def field_agent_create(request):
    if not _owner_agent_access(request):
        return render(request, "khataapp/agent_locked.html")

    selected_member = None
    if request.method == "POST":
        form = FieldAgentForm(request.POST, owner=request.user)
        try:
            selected_member = form.fields["user"].queryset.filter(id=request.POST.get("user")).first()
        except Exception:
            selected_member = None
        if form.is_valid():
            agent = form.save(commit=False)
            agent.owner = request.user
            agent.save()
            form.save_m2m()
            _save_agent_access_controls(request, agent.user, agent.role)
            messages.success(request, "Field agent created successfully.")
            return redirect("khataapp:field_agent_list")
    else:
        form = FieldAgentForm(owner=request.user)

    context = {"form": form, "mode": "create", "selected_member": selected_member}
    context.update(_agent_access_context(selected_member))
    return render(request, "khataapp/agent_form.html", context)


@login_required
def field_agent_edit(request, agent_id):
    if not _owner_agent_access(request):
        return render(request, "khataapp/agent_locked.html")

    agent = get_object_or_404(FieldAgent, id=agent_id, owner=request.user)
    if request.method == "POST":
        form = FieldAgentForm(request.POST, instance=agent, owner=request.user)
        if form.is_valid():
            agent = form.save()
            _save_agent_access_controls(request, agent.user, agent.role)
            messages.success(request, "Field agent updated successfully.")
            return redirect("khataapp:field_agent_list")
    else:
        form = FieldAgentForm(instance=agent, owner=request.user)

    context = {"form": form, "mode": "edit", "agent": agent, "selected_member": agent.user}
    context.update(_agent_access_context(agent.user))
    return render(request, "khataapp/agent_form.html", context)


@login_required
def field_agent_generate_link(request, agent_id):
    if not _owner_agent_access(request):
        return render(request, "khataapp/agent_locked.html")

    agent = get_object_or_404(FieldAgent, id=agent_id, owner=request.user)

    mobile = agent.mobile or agent.user.mobile
    if not mobile:
        messages.warning(request, "Agent mobile number is missing.")
        return redirect("khataapp:field_agent_list")

    link = LoginLink.objects.create(
        user=agent.user,
        purpose="dashboard",
        expires_at=timezone.now() + timedelta(days=7),
    )

    url = request.build_absolute_uri(
        reverse("accounts:login_link", args=[link.token])
    )
    message = f"Click here for more details 👉 {url}"

    OfflineMessage.objects.create(
        party=None,
        recipient_name=agent.user.get_full_name() or agent.user.email,
        recipient_mobile=mobile,
        message=message,
        channel="whatsapp",
        status="pending"
    )

    messages.success(request, "Agent login link queued.")
    return redirect("khataapp:field_agent_list")


@login_required
def supplier_detail(request, supplier_id):
    """Detailed view of a supplier's transactions and outstanding amounts"""
    supplier = get_object_or_404(Party, id=supplier_id, owner=request.user, party_type='supplier')

    # Get outstanding orders
    outstanding_orders = Order.objects.filter(
        party=supplier,
        order_type='PURCHASE',
        due_amount__gt=0
    ).order_by('payment_due_date')

    # Get payment history
    payments = SupplierPayment.objects.filter(
        supplier=supplier
    ).select_related('order').order_by('-payment_date')

    # Get supplier summary
    suppliers_data = SupplierService.get_supplier_summary(request.user)
    summary = next((s for s in suppliers_data if s['id'] == supplier.id), {})

    # Get ledger
    ledger = SupplierService.get_supplier_ledger(supplier)

    context = {
        'supplier': supplier,
        'outstanding_orders': outstanding_orders,
        'payments': payments,
        'summary': summary,
        'ledger': ledger,
        'today': timezone.now().date(),
        'due_soon_date': timezone.now().date() + timedelta(days=7),
    }
    return render(request, 'khataapp/supplier_detail.html', context)


@login_required
def add_supplier_payment(request):
    """Add payment to supplier for outstanding purchase"""
    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.cleaned_data['order']
            payment = SupplierService.process_supplier_payment(
                order=order,
                amount=form.cleaned_data['amount'],
                payment_mode=form.cleaned_data['payment_mode'],
                reference=form.cleaned_data.get('reference'),
                notes=form.cleaned_data.get('notes'),
                payment_date=form.cleaned_data.get('payment_date')
            )

            messages.success(request, f"Payment of ₹{payment.amount} added successfully!")
            return redirect('khataapp:supplier_detail', supplier_id=order.party.id)
    else:
        form = SupplierPaymentForm(user=request.user)

        # Pre-select supplier if provided in query params
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            try:
                supplier = Party.objects.get(id=supplier_id, owner=request.user, party_type='supplier')
                # Filter orders for this supplier
                form.fields['order'].queryset = Order.objects.filter(
                    party=supplier,
                    order_type='PURCHASE',
                    due_amount__gt=0
                )
            except Party.DoesNotExist:
                pass

        # Pre-select order if provided in query params
        order_id = request.GET.get('order')
        if order_id:
            try:
                order = Order.objects.get(id=order_id, owner=request.user, order_type='PURCHASE')
                form.initial['order'] = order
            except Order.DoesNotExist:
                pass

    return render(request, 'khataapp/add_supplier_payment.html', {'form': form})

    
