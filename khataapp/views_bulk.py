from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import reverse

from accounts.forms import CSVUploadForm
from accounts.roles import can_edit
from khataapp.models import Party, Transaction as PartyTransaction


def _csv_to_dict_rows(uploaded_file) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        raw = uploaded_file.read()
        text = raw.decode("utf-8-sig", errors="ignore")
    except Exception:
        return [], ["Unable to read file. Please upload a valid UTF-8 CSV."]

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["Missing CSV headers."]

    rows: list[dict[str, str]] = []
    for idx, row in enumerate(reader, start=2):  # header line = 1
        if idx > 2002:
            errors.append("CSV too large. Max 2000 data rows allowed per upload.")
            break
        cleaned = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
        # Skip completely empty rows
        if not any(cleaned.values()):
            continue
        cleaned["_line"] = str(idx)
        rows.append(cleaned)

    return rows, errors


@login_required
def party_sample_csv(request):
    content = "name,mobile,email,party_type\nAcme Traders,9876543210,acme@example.com,customer\n"
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="party_sample.csv"'
    return resp


@login_required
def party_bulk_upload(request):
    if not can_edit(request.user):
        messages.error(request, "Permission denied. (Role: view-only)")
        return redirect("khataapp:party_list")

    session_key = "kp_bulk_party_rows"
    preview_rows: list[list[str]] | None = None
    preview_total: int | None = None
    preview_headers = ["Line", "Name", "Mobile", "Email", "Type"]
    errors: list[str] = []

    if request.method == "POST" and request.POST.get("confirm"):
        payload = request.session.pop(session_key, None) or []
        created_count = 0
        with transaction.atomic():
            for item in payload:
                name = (item.get("name") or "").strip()
                mobile = (item.get("mobile") or "").strip()
                email = (item.get("email") or "").strip()
                party_type = (item.get("party_type") or "customer").strip().lower()

                defaults = {
                    "owner": request.user,
                    "name": name,
                    "mobile": mobile,
                    "email": email,
                    "party_type": party_type,
                }

                # Prefer mobile as stable key if provided.
                if mobile:
                    _, created = Party.objects.update_or_create(owner=request.user, mobile=mobile, defaults=defaults)
                else:
                    _, created = Party.objects.update_or_create(owner=request.user, name=name, defaults=defaults)
                if created:
                    created_count += 1

        messages.success(request, f"Saved Successfully: {created_count} parties imported.")
        return redirect("khataapp:party_list")

    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and not request.POST.get("confirm"):
        if form.is_valid():
            dict_rows, read_errors = _csv_to_dict_rows(form.cleaned_data["file"])
            errors.extend(read_errors)

            validated: list[dict[str, str]] = []
            preview_total = len(dict_rows)

            for row in dict_rows:
                line = row.get("_line") or "?"
                name = (row.get("name") or "").strip()
                mobile = (row.get("mobile") or "").strip()
                email = (row.get("email") or "").strip()
                party_type = (row.get("party_type") or "customer").strip().lower()

                if not name:
                    errors.append(f"Line {line}: name is required.")
                    continue
                if party_type not in {"customer", "supplier"}:
                    errors.append(f"Line {line}: party_type must be customer/supplier.")
                    continue

                validated.append(
                    {
                        "name": name,
                        "mobile": mobile,
                        "email": email,
                        "party_type": party_type,
                    }
                )

            request.session[session_key] = validated if not errors else []
            preview_rows = [
                [str(i + 1), r["name"], r.get("mobile", ""), r.get("email", ""), r["party_type"]]
                for i, r in enumerate(validated[:50])
            ]

    return render(
        request,
        "khataapp/party_bulk_upload.html",
        {
            "form": form,
            "page_title": "Bulk Add Parties",
            "page_subtitle": "Upload a CSV to create/update parties (preview before import).",
            "sample_url": reverse("khataapp:party_sample_csv"),
            "back_url": reverse("khataapp:party_list"),
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "errors": errors,
        },
    )


@login_required
def transaction_sample_csv(request):
    content = "party_mobile,party_name,txn_type,txn_mode,amount,date,notes\n9876543210,,credit,cash,500,2026-02-27,Payment received\n"
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="transaction_sample.csv"'
    return resp


@login_required
def transaction_bulk_upload(request):
    if not can_edit(request.user):
        messages.error(request, "Permission denied. (Role: view-only)")
        return redirect("khataapp:transaction_list")

    session_key = "kp_bulk_txn_rows"
    preview_headers = ["Line", "Party", "Type", "Mode", "Amount", "Date", "Notes"]
    preview_rows: list[list[str]] | None = None
    preview_total: int | None = None
    errors: list[str] = []

    if request.method == "POST" and request.POST.get("confirm"):
        payload = request.session.pop(session_key, None) or []
        created_count = 0
        with transaction.atomic():
            for item in payload:
                party = Party.objects.get(id=item["party_id"], owner=request.user)
                PartyTransaction.objects.create(
                    party=party,
                    txn_type=item["txn_type"],
                    txn_mode=item["txn_mode"],
                    amount=Decimal(item["amount"]),
                    date=datetime.fromisoformat(item["date"]).date(),
                    notes=item.get("notes") or "",
                )
                created_count += 1

        messages.success(request, f"Saved Successfully: {created_count} transactions imported.")
        return redirect("khataapp:transaction_list")

    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and not request.POST.get("confirm"):
        if form.is_valid():
            dict_rows, read_errors = _csv_to_dict_rows(form.cleaned_data["file"])
            errors.extend(read_errors)
            preview_total = len(dict_rows)

            validated: list[dict] = []
            for row in dict_rows:
                line = row.get("_line") or "?"
                party_mobile = (row.get("party_mobile") or "").strip()
                party_name = (row.get("party_name") or "").strip()
                txn_type = (row.get("txn_type") or "").strip().lower()
                txn_mode = (row.get("txn_mode") or "cash").strip().lower()
                amount_raw = (row.get("amount") or "").strip()
                date_raw = (row.get("date") or "").strip()
                notes = (row.get("notes") or "").strip()

                if txn_type not in {"credit", "debit"}:
                    errors.append(f"Line {line}: txn_type must be credit/debit.")
                    continue
                valid_modes = {c for c, _ in PartyTransaction.TXN_MODE_CHOICES}
                if txn_mode not in valid_modes:
                    errors.append(f"Line {line}: txn_mode invalid. Use one of: {', '.join(sorted(valid_modes))}.")
                    continue

                try:
                    amount = Decimal(amount_raw)
                except (InvalidOperation, TypeError):
                    errors.append(f"Line {line}: amount must be a number.")
                    continue
                if amount <= 0:
                    errors.append(f"Line {line}: amount must be > 0.")
                    continue

                if date_raw:
                    try:
                        date = datetime.fromisoformat(date_raw).date()
                    except Exception:
                        errors.append(f"Line {line}: date must be YYYY-MM-DD.")
                        continue
                else:
                    date = timezone.localdate()

                party = None
                if party_mobile:
                    party = Party.objects.filter(owner=request.user, mobile=party_mobile).first()
                if not party and party_name:
                    party = Party.objects.filter(owner=request.user, name__iexact=party_name).first()
                if not party:
                    errors.append(f"Line {line}: party not found (provide party_mobile or party_name).")
                    continue

                validated.append(
                    {
                        "party_id": party.id,
                        "party_label": party.name,
                        "txn_type": txn_type,
                        "txn_mode": txn_mode,
                        "amount": str(amount),
                        "date": date.isoformat(),
                        "notes": notes,
                    }
                )

            request.session[session_key] = validated if not errors else []
            preview_rows = [
                [
                    str(i + 1),
                    r["party_label"],
                    r["txn_type"],
                    r["txn_mode"],
                    r["amount"],
                    r["date"],
                    r.get("notes") or "",
                ]
                for i, r in enumerate(validated[:50])
            ]

    return render(
        request,
        "khataapp/transaction_bulk_upload.html",
        {
            "form": form,
            "page_title": "Bulk Add Transactions",
            "page_subtitle": "Upload a CSV to create transactions (preview before import).",
            "sample_url": reverse("khataapp:transaction_sample_csv"),
            "back_url": reverse("khataapp:transaction_list"),
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "errors": errors,
        },
    )
