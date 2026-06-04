from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.utils import OperationalError
from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils import timezone

from ledger.services import reporting as gl_reports


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return default


def _default_range(request):
    today = timezone.now().date()
    date_to = _parse_date(request.GET.get("to"), today)
    date_from = _parse_date(request.GET.get("from"), date_to - timedelta(days=30))
    return date_from, date_to


@login_required
def trial_balance(request):
    date_from, date_to = _default_range(request)
    db_not_ready = False
    try:
        data = gl_reports.trial_balance(owner=request.user, date_from=date_from, date_to=date_to)
    except OperationalError as e:
        # Friendly fallback for dev DBs that haven't been migrated yet.
        msg = str(e).lower()
        if "no such table" in msg or "does not exist" in msg:
            db_not_ready = True
            data = {
                "rows": [],
                "totals": {
                    "opening_debit": gl_reports.DECIMAL_ZERO,
                    "opening_credit": gl_reports.DECIMAL_ZERO,
                    "period_debit": gl_reports.DECIMAL_ZERO,
                    "period_credit": gl_reports.DECIMAL_ZERO,
                    "closing_debit": gl_reports.DECIMAL_ZERO,
                    "closing_credit": gl_reports.DECIMAL_ZERO,
                },
                "date_from": date_from,
                "date_to": date_to,
                "warning": "Database tables missing. Run migrations to enable ledger reports.",
            }
        else:
            raise

    wants_json = (request.GET.get("format") or "").lower() == "json" or "application/json" in (request.headers.get("Accept") or "")
    if wants_json:
        return JsonResponse(data)

    if (request.GET.get("download") or "").lower() == "csv":
        import csv

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="trial_balance_{date_from.isoformat()}_{date_to.isoformat()}.csv"'
        w = csv.writer(resp)
        w.writerow(["Code", "Name", "Type", "Opening DR", "Opening CR", "Period DR", "Period CR", "Closing DR", "Closing CR"])
        for r in data.get("rows", []):
            w.writerow(
                [
                    r.get("code", ""),
                    r.get("name", ""),
                    r.get("account_type", ""),
                    r.get("opening_debit", "0.00"),
                    r.get("opening_credit", "0.00"),
                    r.get("debit", "0.00"),
                    r.get("credit", "0.00"),
                    r.get("closing_debit", "0.00"),
                    r.get("closing_credit", "0.00"),
                ]
            )
        return resp

    return render(
        request,
        "reports/erp/trial_balance.html",
        {
            "rows": data.get("rows", []),
            "totals": data.get("totals", {}),
            "date_from": date_from,
            "date_to": date_to,
            "db_not_ready": db_not_ready,
        },
    )


@login_required
def profit_loss(request):
    date_from, date_to = _default_range(request)
    data = gl_reports.profit_and_loss(owner=request.user, date_from=date_from, date_to=date_to)
    return JsonResponse(data)


@login_required
def balance_sheet(request):
    today = timezone.now().date()
    as_of = _parse_date(request.GET.get("as_of"), today)
    pnl_from = request.GET.get("pnl_from")
    pnl_from_date = _parse_date(pnl_from, None) if pnl_from else None
    data = gl_reports.balance_sheet(owner=request.user, as_of=as_of, pnl_from=pnl_from_date)
    return JsonResponse(data)


@login_required
def day_book(request):
    date_from, date_to = _default_range(request)
    data = gl_reports.day_book(owner=request.user, date_from=date_from, date_to=date_to)
    return JsonResponse(data)


@login_required
def cash_book(request):
    date_from, date_to = _default_range(request)
    data = gl_reports.cash_book(owner=request.user, date_from=date_from, date_to=date_to)
    return JsonResponse(data)


@login_required
def bank_book(request):
    date_from, date_to = _default_range(request)
    data = gl_reports.bank_book(owner=request.user, date_from=date_from, date_to=date_to)
    return JsonResponse(data)


@login_required
def ledger_statement(request):
    account_code = (request.GET.get("account_code") or "").strip().upper() or None
    account_id_raw = (request.GET.get("account_id") or "").strip()
    party_id_raw = (request.GET.get("party_id") or "").strip()

    account_id = int(account_id_raw) if account_id_raw.isdigit() else None
    party_id = int(party_id_raw) if party_id_raw.isdigit() else None

    date_from, date_to = _default_range(request)
    data = gl_reports.ledger_statement(
        owner=request.user,
        account_code=account_code,
        account_id=account_id,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
    )
    return JsonResponse(data)


@login_required
def party_outstanding(request):
    today = timezone.now().date()
    as_of = _parse_date(request.GET.get("as_of"), today)
    data = gl_reports.party_outstanding(owner=request.user, as_of=as_of)
    return JsonResponse(data)


@login_required
def warehouse_stock(request):
    today = timezone.now().date()
    as_of = _parse_date(request.GET.get("as_of"), today)
    data = gl_reports.warehouse_stock(owner=request.user, as_of=as_of)
    return JsonResponse(data)


@login_required
def product_movement(request, product_id: int):
    warehouse_id_raw = (request.GET.get("warehouse_id") or "").strip()
    warehouse_id = int(warehouse_id_raw) if warehouse_id_raw.isdigit() else None
    date_from, date_to = _default_range(request)
    data = gl_reports.product_movement(
        owner=request.user,
        product_id=product_id,
        warehouse_id=warehouse_id,
        date_from=date_from,
        date_to=date_to,
    )
    return JsonResponse(data)


@login_required
def gst_summary(request):
    date_from, date_to = _default_range(request)
    data = gl_reports.gst_summary_gstr1_base(owner=request.user, date_from=date_from, date_to=date_to)
    return JsonResponse(data)
