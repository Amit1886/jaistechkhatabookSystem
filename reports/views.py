from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_date
from django.utils.timezone import now

from billing.services import user_has_feature
from khataapp.models import Party, Transaction
from khataapp.models import CreditAccount, CreditSettings
from commerce.models import Product, StockEntry, Quotation
from ledger.models import LedgerAccount
from ledger.services import reporting as gl_reports
from reports.forms import ChecklistForm, ChecklistItemForm, QueryTicketForm
from reports.models import Checklist, ChecklistItem, QueryTicket
from apps.platform.identity.models import AuditLog, TenantMembership


# Create your views here.
def _date_range(request):
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    return date_from, date_to


@login_required
def stock_summary(request):
    q = (request.GET.get("q") or "").strip()
    products = Product.objects.filter(owner=request.user).annotate(
        total_in=Sum(
            Case(
                When(stockentry__entry_type='IN', then=F('stockentry__quantity')),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ),
        total_out=Sum(
            Case(
                When(stockentry__entry_type='OUT', then=F('stockentry__quantity')),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ),
        net_stock=F('total_in') - F('total_out')
    )
    if q:
        products = products.filter(name__icontains=q)

    return render(request, 'reports/stock_summary.html', {
        'products': products,
        "q": q,
    })


def save_sale(product, qty, party, amount):
    Transaction.objects.create(
        party=party,
        txn_type='credit',
        txn_mode='cash',
        amount=amount,
        date=now().date(),
        voucher_type="stock_sale",
        created_by=getattr(party, "owner", None),
    )

    StockEntry.objects.create(
        product=product,
        quantity=qty,
        entry_type='OUT',
        date=now().date()
    )

@login_required
def all_transactions(request):
    date_from, date_to = _date_range(request)
    transactions = Transaction.objects.select_related("party").filter(party__owner=request.user).order_by("-date", "-id")
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)

    totals = transactions.aggregate(
        credit_total=Sum(
            Case(
                When(txn_type="credit", then=F("amount")),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
        debit_total=Sum(
            Case(
                When(txn_type="debit", then=F("amount")),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ),
    )
    return render(request, 'reports/all_transactions.html', {
        'transactions': transactions,
        "credit_total": totals.get("credit_total") or Decimal("0.00"),
        "debit_total": totals.get("debit_total") or Decimal("0.00"),
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def cash_book(request):
    date_from, date_to = _date_range(request)
    transactions = Transaction.objects.filter(party__owner=request.user, txn_mode="cash").select_related("party")
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)

    total_in = transactions.filter(txn_type='credit').aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_out = transactions.filter(txn_type='debit').aggregate(
        total=Sum('amount')
    )['total'] or 0

    return render(request, 'reports/cash_book.html', {
        'transactions': transactions,
        'total_in': total_in,
        'total_out': total_out,
        'balance': total_in - total_out,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def voucher_report(request):
    date_from, date_to = _date_range(request)
    vouchers = Transaction.objects.filter(party__owner=request.user).select_related("party").order_by("-date", "-id")
    if date_from:
        vouchers = vouchers.filter(date__gte=date_from)
    if date_to:
        vouchers = vouchers.filter(date__lte=date_to)
    return render(request, 'reports/voucher_report.html', {
        'vouchers': vouchers
    })


@login_required
def sales_report(request):
    date_from, date_to = _date_range(request)
    sales = Transaction.objects.filter(party__owner=request.user, txn_type="credit").select_related("party")
    if date_from:
        sales = sales.filter(date__gte=date_from)
    if date_to:
        sales = sales.filter(date__lte=date_to)

    total_sales = sales.aggregate(
        total=Sum('amount')
    )['total'] or 0

    return render(request, 'reports/sales_report.html', {
        'sales': sales,
        'total_sales': total_sales,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def purchase_report(request):
    date_from, date_to = _date_range(request)
    purchases = Transaction.objects.filter(party__owner=request.user, txn_type="debit").select_related("party")
    if date_from:
        purchases = purchases.filter(date__gte=date_from)
    if date_to:
        purchases = purchases.filter(date__lte=date_to)

    total_purchase = purchases.aggregate(
        total=Sum('amount')
    )['total'] or 0

    return render(request, 'reports/purchase_report.html', {
        'purchases': purchases,
        'total_purchase': total_purchase,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def quotation_report(request):
    date_from, date_to = _date_range(request)
    party_id = (request.GET.get("party") or "").strip()
    status = (request.GET.get("status") or "").strip()

    parties = Party.objects.filter(owner=request.user).order_by("name")

    try:
        quotations = Quotation.objects.select_related("party").filter(party__owner=request.user).order_by("-date", "-id")
        if date_from:
            quotations = quotations.filter(date__gte=date_from)
        if date_to:
            quotations = quotations.filter(date__lte=date_to)
        if party_id:
            quotations = quotations.filter(party_id=party_id)
        if status:
            quotations = quotations.filter(status=status)

        money_field = DecimalField(max_digits=14, decimal_places=2)
        totals = quotations.aggregate(
            total=Coalesce(
                Sum("total_amount"),
                Value(0, output_field=money_field),
                output_field=money_field,
            )
        )
        total_amount = totals.get("total") or Decimal("0.00")
    except OperationalError:
        quotations = Quotation.objects.none()
        total_amount = Decimal("0.00")
        messages.error(request, "Quotation module database tables missing. Please run migrations.")

    return render(request, "reports/quotation_report.html", {
        "quotations": quotations,
        "parties": parties,
        "statuses": Quotation.Status.choices,
        "selected_party": party_id,
        "selected_status": status,
        "total_amount": total_amount,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def low_stock(request):
    products = list(Product.objects.filter(owner=request.user, stock__lte=F("min_stock")).order_by("name"))

    popup_product = None
    popup_best = None
    try:
        from procurement.services import best_supplier_map_for_products

        best_map = best_supplier_map_for_products(request.user, [int(p.id) for p in products])
        for p in products:
            best = best_map.get(int(p.id))
            setattr(p, "best_supplier", best)
            if not popup_product and best is not None:
                popup_product = p
                popup_best = best
    except Exception:
        for p in products:
            setattr(p, "best_supplier", None)

    return render(request, 'reports/low_stock.html', {
        'products': products,
        'popup_product': popup_product,
        'popup_best': popup_best,
    })


@login_required
def party_ledger(request):
    party_id = request.GET.get("party")
    date_from, date_to = _date_range(request)

    parties = Party.objects.filter(owner=request.user).order_by("name")
    transactions = Transaction.objects.none()

    if party_id:
        transactions = Transaction.objects.filter(party_id=party_id, party__owner=request.user).order_by("date", "id")
        if date_from:
            transactions = transactions.filter(date__gte=date_from)
        if date_to:
            transactions = transactions.filter(date__lte=date_to)

    return render(request, 'reports/party_ledger.html', {
        'parties': parties,
        'transactions': transactions,
        'selected_party': party_id,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def outstanding(request):
    parties = (
        Party.objects.filter(owner=request.user)
        .annotate(
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
        )
        .annotate(balance=F("debit_total") - F("credit_total"))
        .order_by("name")
    )

    return render(request, 'reports/outstanding.html', {
        'parties': parties
    })


@login_required
def profit_loss(request):
    date_from, date_to = _date_range(request)
    txns = Transaction.objects.filter(party__owner=request.user)
    if date_from:
        txns = txns.filter(date__gte=date_from)
    if date_to:
        txns = txns.filter(date__lte=date_to)

    income = txns.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    expense = txns.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return render(request, 'reports/profit_loss.html', {
        'income': income,
        'expense': expense,
        'profit': income - expense,
        "date_from": date_from,
        "date_to": date_to,
    })


@login_required
def day_book(request):
    selected = parse_date(request.GET.get("date") or "") or now().date()
    transactions = Transaction.objects.filter(party__owner=request.user, date=selected).select_related("party")

    return render(request, 'reports/day_book.html', {
        'transactions': transactions,
        'date': selected
    })


@login_required
def audit_trail(request):
    date_from, date_to = _date_range(request)
    action = (request.GET.get("action") or "").strip()
    object_type = (request.GET.get("object_type") or "").strip()
    q = (request.GET.get("q") or "").strip()

    tenant_ids = list(
        TenantMembership.objects.filter(user=request.user, is_active=True).values_list("tenant_id", flat=True)
    )
    audit_logs = AuditLog.objects.select_related("tenant", "user").order_by("-created_at")
    if tenant_ids:
        audit_logs = audit_logs.filter(Q(tenant_id__in=tenant_ids) | Q(user=request.user))
    elif not request.user.is_superuser:
        audit_logs = audit_logs.filter(user=request.user)

    if date_from:
        audit_logs = audit_logs.filter(created_at__date__gte=date_from)
    if date_to:
        audit_logs = audit_logs.filter(created_at__date__lte=date_to)
    if action:
        audit_logs = audit_logs.filter(action__icontains=action)
    if object_type:
        audit_logs = audit_logs.filter(object_type__icontains=object_type)
    if q:
        audit_logs = audit_logs.filter(
            Q(action__icontains=q)
            | Q(object_type__icontains=q)
            | Q(object_id__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
        )

    audit_logs = audit_logs[:300]
    return render(
        request,
        "reports/audit_trail.html",
        {
            "audit_logs": audit_logs,
            "date_from": date_from,
            "date_to": date_to,
            "action": action,
            "object_type": object_type,
            "q": q,
        },
    )


def _require_feature(request, feature_key: str, feature_label: str):
    if user_has_feature(request.user, feature_key):
        return None
    return render(request, "core/upgrade_required.html", {"feature_label": feature_label}, status=403)


@login_required
def account_summary(request):
    denied = _require_feature(request, "reports.account_summary", "Account Summary")
    if denied:
        return denied

    try:
        money_field = DecimalField(max_digits=14, decimal_places=2)
        accounts = (
            LedgerAccount.objects.filter(owner=request.user)
            .values("id", "code", "name", "account_type", "is_system")
            .annotate(
                debit=Coalesce(Sum("entries__debit"), Value(0, output_field=money_field)),
                credit=Coalesce(Sum("entries__credit"), Value(0, output_field=money_field)),
            )
            .annotate(balance=F("debit") - F("credit"))
            .order_by("code")
        )
    except OperationalError:
        messages.warning(request, "Ledger tables not ready. Run migrations to enable this report.")
        accounts = []

    return render(request, "reports/modules/account_summary.html", {"accounts": accounts})


@login_required
def inventory_summary(request):
    denied = _require_feature(request, "reports.inventory_summary", "Inventory Summary")
    if denied:
        return denied

    as_of = parse_date((request.GET.get("as_of") or "").strip()) or now().date()
    try:
        data = gl_reports.warehouse_stock(owner=request.user, as_of=as_of)
    except OperationalError:
        messages.warning(request, "Stock ledger tables not ready. Run migrations to enable this report.")
        data = {"rows": []}
    return render(request, "reports/modules/inventory_summary.html", {"as_of": as_of, "rows": data.get("rows", [])})


@login_required
def inventory_books(request):
    denied = _require_feature(request, "reports.inventory_books", "Inventory Books")
    if denied:
        return denied

    product_id_raw = (request.GET.get("product_id") or "").strip()
    warehouse_id_raw = (request.GET.get("warehouse_id") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    product_id = int(product_id_raw) if product_id_raw.isdigit() else None
    warehouse_id = int(warehouse_id_raw) if warehouse_id_raw.isdigit() else None

    products = Product.objects.filter(owner=request.user).order_by("name").only("id", "name")
    movement = None
    if product_id:
        try:
            movement = gl_reports.product_movement(
                owner=request.user,
                product_id=product_id,
                warehouse_id=warehouse_id,
                date_from=date_from,
                date_to=date_to,
            )
        except OperationalError:
            messages.warning(request, "Stock ledger tables not ready. Run migrations to enable this report.")
            movement = {"rows": []}

    return render(
        request,
        "reports/modules/inventory_books.html",
        {
            "products": products,
            "selected_product_id": product_id,
            "selected_warehouse_id": warehouse_id,
            "date_from": date_from,
            "date_to": date_to,
            "rows": (movement or {}).get("rows", []) if movement else [],
        },
    )


@login_required
def gst_report(request):
    denied = _require_feature(request, "reports.gst_report", "GST Report")
    if denied:
        return denied

    date_from = parse_date(request.GET.get("from") or "") or (now().date().replace(day=1))
    date_to = parse_date(request.GET.get("to") or "") or now().date()
    try:
        data = gl_reports.gst_summary_gstr1_base(owner=request.user, date_from=date_from, date_to=date_to)
    except OperationalError:
        messages.warning(request, "Ledger tables not ready. Run migrations to enable this report.")
        data = {"summary": [], "invoices": []}
    return render(
        request,
        "reports/modules/gst_report.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "summary": data.get("summary", []),
            "invoices": data.get("invoices", []),
        },
    )


@login_required
def mis_report(request):
    denied = _require_feature(request, "reports.mis_report", "MIS Report")
    if denied:
        return denied

    date_from, date_to = _date_range(request)
    txns = Transaction.objects.filter(party__owner=request.user)
    if date_from:
        txns = txns.filter(date__gte=date_from)
    if date_to:
        txns = txns.filter(date__lte=date_to)

    income = txns.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    expense = txns.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return render(
        request,
        "reports/modules/mis_report.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "income": income,
            "expense": expense,
            "profit": income - expense,
        },
    )


@login_required
def interest_calculation(request):
    denied = _require_feature(request, "reports.interest_calculation", "Interest Calculation")
    if denied:
        return denied

    settings_obj = CreditSettings.objects.order_by("-created_at").first()
    annual_rate = (settings_obj.interest_rate if settings_obj else Decimal("0.00")) or Decimal("0.00")

    accounts = (
        CreditAccount.objects.select_related("party")
        .filter(party__owner=request.user)
        .order_by("party__name")
    )

    rows = []
    for acc in accounts:
        outstanding = (acc.outstanding or Decimal("0.00"))
        monthly_interest = (outstanding * annual_rate / Decimal("100.00")) / Decimal("12.00")
        rows.append(
            {
                "party": acc.party.name,
                "outstanding": outstanding,
                "annual_rate": annual_rate,
                "monthly_interest": monthly_interest.quantize(Decimal("0.01")),
            }
        )

    return render(
        request,
        "reports/modules/interest_calculation.html",
        {"annual_rate": annual_rate, "rows": rows},
    )


@login_required
def checklist_list(request):
    denied = _require_feature(request, "system.checklist", "Checklist System")
    if denied:
        return denied

    if request.method == "POST":
        form = ChecklistForm(request.POST)
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.owner = request.user
            checklist.save()
            messages.success(request, "Checklist saved.")
            return redirect("reports:checklist_list")
    else:
        form = ChecklistForm()

    checklists = Checklist.objects.filter(owner=request.user).prefetch_related("items").order_by("-created_at")
    return render(request, "reports/checklist_list.html", {"form": form, "checklists": checklists})


@login_required
def checklist_detail(request, checklist_id: int):
    denied = _require_feature(request, "system.checklist", "Checklist System")
    if denied:
        return denied

    checklist = get_object_or_404(Checklist, id=checklist_id, owner=request.user)

    if request.method == "POST":
        item_form = ChecklistItemForm(request.POST)
        if item_form.is_valid():
            item = item_form.save(commit=False)
            item.checklist = checklist
            item.sort_order = checklist.items.count()
            item.save()
            messages.success(request, "Item saved.")
            return redirect("reports:checklist_detail", checklist_id=checklist.id)
    else:
        item_form = ChecklistItemForm()

    items = checklist.items.all().order_by("sort_order", "id")
    return render(
        request,
        "reports/checklist_detail.html",
        {"checklist": checklist, "items": items, "item_form": item_form},
    )


@login_required
def checklist_item_toggle(request, checklist_id: int, item_id: int):
    denied = _require_feature(request, "system.checklist", "Checklist System")
    if denied:
        return denied

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)

    checklist = get_object_or_404(Checklist, id=checklist_id, owner=request.user)
    item = get_object_or_404(ChecklistItem, id=item_id, checklist=checklist)
    item.is_done = not bool(item.is_done)
    item.save(update_fields=["is_done", "updated_at"])

    wants_json = "application/json" in (request.headers.get("Accept") or "") or (request.headers.get("X-Requested-With") == "XMLHttpRequest")
    if wants_json:
        return JsonResponse({"ok": True, "is_done": item.is_done})

    messages.success(request, "Item updated.")
    return redirect("reports:checklist_detail", checklist_id=checklist.id)


@login_required
def query_list(request):
    denied = _require_feature(request, "system.query", "Query System")
    if denied:
        return denied

    tickets = QueryTicket.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "reports/query_list.html", {"tickets": tickets})


@login_required
def query_create(request):
    denied = _require_feature(request, "system.query", "Query System")
    if denied:
        return denied

    if request.method == "POST":
        form = QueryTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.owner = request.user
            ticket.save()
            messages.success(request, "Query saved.")
            return redirect("reports:query_detail", ticket_id=ticket.id)
    else:
        form = QueryTicketForm()

    return render(request, "reports/query_form.html", {"form": form})


@login_required
def query_detail(request, ticket_id: int):
    denied = _require_feature(request, "system.query", "Query System")
    if denied:
        return denied

    ticket = get_object_or_404(QueryTicket, id=ticket_id, owner=request.user)

    if request.method == "POST":
        form = QueryTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, "Query updated.")
            return redirect("reports:query_detail", ticket_id=ticket.id)
    else:
        form = QueryTicketForm(instance=ticket)

    return render(request, "reports/query_detail.html", {"ticket": ticket, "form": form})
