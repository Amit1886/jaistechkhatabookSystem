from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.forms import CSVUploadForm
from accounts.roles import can_edit
from commerce.models import Category, Invoice, Payment, Product


_DECIMAL_TOKEN_RE = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")
_BULK_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")

logger = logging.getLogger(__name__)


def _token_hint(token: str | None) -> str:
    token = (token or "").strip().lower()
    if not token:
        return ""
    if len(token) <= 12:
        return token
    return f"{token[:8]}...{token[-4:]}"


def _clean_numeric_text(value: str | None) -> str:
    text = (value or "").strip().replace("\x00", "").replace("\u00A0", " ").replace("\u2212", "-")
    if not text:
        return ""

    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    text = text.replace("%", "")
    for token in ("\u20B9", "$", "\u20AC", "\u00A3", "INR", "Rs.", "Rs", "rs.", "rs"):
        text = text.replace(token, "")

    text = text.strip().replace(" ", "").replace("_", "").lstrip("+")

    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        if text.count(",") > 1:
            text = text.replace(",", "")
        else:
            left, right = text.split(",", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                text = f"{left}.{right}"
            else:
                text = f"{left}{right}"

    return text


def _parse_decimal_field(value: str | None, *, default: Decimal | None = None) -> Decimal:
    cleaned = _clean_numeric_text(value)
    if cleaned == "":
        if default is None:
            raise InvalidOperation("empty")
        return default
    if not _DECIMAL_TOKEN_RE.fullmatch(cleaned):
        raise InvalidOperation(cleaned)
    return Decimal(cleaned)


def _parse_int_field(value: str | None, *, default: int = 0) -> int:
    dec = _parse_decimal_field(value, default=Decimal(str(default)))
    if dec != dec.to_integral_value():
        raise ValueError("not-integer")
    return int(dec)


def _use_file_staging() -> bool:
    return bool(getattr(settings, "DESKTOP_MODE", False))


def _bulk_staging_dir() -> Path:
    base = getattr(settings, "DESKTOP_DATA_DIR", None)
    try:
        base_path = base if isinstance(base, Path) else Path(str(base))
    except Exception:
        base_path = Path.cwd()
    path = (base_path / "bulk_uploads").resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def _bulk_stage_write(*, kind: str, user_id: int, rows: list[dict]) -> str:
    token = uuid.uuid4().hex
    path = (_bulk_staging_dir() / f"{kind}-{int(user_id)}-{token}.json").resolve()
    payload = {"kind": kind, "user_id": int(user_id), "rows": rows, "ts": int(time.time())}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "Bulk upload preview staged (kind=%s user=%s token=%s rows=%s path=%s)",
        kind,
        int(user_id),
        _token_hint(token),
        len(rows or []),
        str(path),
    )
    return token


def _bulk_stage_read(*, kind: str, user_id: int, token: str) -> list[dict]:
    token = (token or "").strip().lower()
    if not _BULK_TOKEN_RE.fullmatch(token):
        return []
    path = (_bulk_staging_dir() / f"{kind}-{int(user_id)}-{token}.json").resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    if str(payload.get("kind") or "") != kind:
        return []
    if int(payload.get("user_id") or 0) != int(user_id):
        return []
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def _bulk_stage_delete(*, kind: str, user_id: int, token: str) -> None:
    token = (token or "").strip().lower()
    if not _BULK_TOKEN_RE.fullmatch(token):
        return
    path = (_bulk_staging_dir() / f"{kind}-{int(user_id)}-{token}.json").resolve()
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _bulk_stage_recent_files(*, kind: str, user_id: int, max_age_seconds: int = 60 * 30) -> list[Path]:
    """
    List recent staging JSON files for this user/kind.

    Used as a safe fallback if the browser doesn't send the hidden bulk_token.
    """
    now = time.time()
    items: list[tuple[float, Path]] = []
    try:
        for p in _bulk_staging_dir().glob(f"{kind}-{int(user_id)}-*.json"):
            try:
                st = p.stat()
            except Exception:
                continue
            age = now - float(getattr(st, "st_mtime", 0.0) or 0.0)
            if age <= max_age_seconds:
                items.append((float(st.st_mtime), p))
    except Exception:
        return []
    items.sort(key=lambda it: it[0], reverse=True)
    return [p for _, p in items]


def _bulk_stage_fallback_read(*, kind: str, user_id: int, token: str) -> tuple[str, list[dict]]:
    """
    Fallback for desktop mode when confirm POST is missing/invalid token.

    Safety: only auto-fallback when there's exactly one recent staged file.
    """
    if _BULK_TOKEN_RE.fullmatch((token or "").strip().lower()):
        return "", []

    recent = _bulk_stage_recent_files(kind=kind, user_id=user_id)
    if len(recent) != 1:
        return "", []

    path = recent[0]
    guessed = ""
    try:
        guessed = (path.stem.split("-")[-1] or "").strip().lower()
    except Exception:
        guessed = ""
    if not _BULK_TOKEN_RE.fullmatch(guessed):
        return "", []

    rows = _bulk_stage_read(kind=kind, user_id=user_id, token=guessed)
    return guessed, rows


def _csv_to_dict_rows(uploaded_file) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        raw = uploaded_file.read()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw.count(b"\x00") > (len(raw) // 10):
            text = raw.decode("utf-16")
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1252")
    except Exception:
        return [], ["Unable to read file. Please upload a valid CSV (UTF-8/UTF-16)."]

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["Missing CSV headers."]

    rows: list[dict[str, str]] = []
    for idx, row in enumerate(reader, start=2):
        if idx > 2002:
            errors.append("CSV too large. Max 2000 data rows allowed per upload.")
            break
        cleaned = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
        if not any(cleaned.values()):
            continue
        cleaned["_line"] = str(idx)
        rows.append(cleaned)

    return rows, errors


@login_required
def product_sample_csv(request):
    content = (
        "name,category,price,stock,min_stock,sku,unit,hsn_code,gst_rate,description\n"
        "Sugar 1kg,Grocery,45.00,50,5,,kg,1701,5,White sugar\n"
    )
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="product_sample.csv"'
    return resp


@login_required
def product_bulk_upload(request):
    if not can_edit(request.user):
        messages.error(request, "Permission denied. (Role: view-only)")
        return redirect("commerce:product_list")

    session_key = "kp_bulk_product_rows"
    preview_headers = ["Line", "Name", "Category", "SKU", "Price", "Stock", "Min", "Unit", "GST%"]
    preview_rows: list[list[str]] | None = None
    preview_total: int | None = None
    errors: list[str] = []
    bulk_token: str | None = None

    if request.method == "POST" and request.POST.get("confirm"):
        desktop_stage = _use_file_staging()
        token = (request.POST.get("bulk_token") or "").strip()
        payload: list[dict] = []
        if desktop_stage:
            payload = _bulk_stage_read(kind="products", user_id=request.user.id, token=token)
            if not payload:
                fallback_token, fallback_payload = _bulk_stage_fallback_read(
                    kind="products",
                    user_id=request.user.id,
                    token=token,
                )
                if fallback_payload:
                    logger.warning(
                        "Bulk upload confirm missing token; using fallback (kind=%s user=%s token=%s fallback=%s)",
                        "products",
                        int(request.user.id),
                        _token_hint(token),
                        _token_hint(fallback_token),
                    )
                    token = fallback_token
                    payload = fallback_payload
        else:
            payload = request.session.pop(session_key, None) or []
        if not payload:
            if desktop_stage:
                try:
                    pending = _bulk_stage_recent_files(kind="products", user_id=request.user.id)
                    logger.warning(
                        "Bulk upload confirm failed (kind=%s user=%s token=%s pending_files=%s)",
                        "products",
                        int(request.user.id),
                        _token_hint(token),
                        len(pending),
                    )
                except Exception:
                    pass
            messages.error(request, "Import failed (preview expired). Please upload the CSV again.")
            return redirect(request.path)

        created_count = 0
        updated_count = 0
        skipped_count = 0
        current_line = ""
        current_sku = ""
        try:
            with transaction.atomic():
                for item in payload:
                    current_line = str(item.get("line") or "")
                    category = None
                    if item.get("category"):
                        category, _ = Category.objects.get_or_create(
                            owner=request.user,
                            name=item["category"],
                            defaults={"description": ""},
                        )

                    defaults = {
                        "owner": request.user,
                        "name": item["name"],
                        "category": category,
                        "price": Decimal(item["price"]),
                        "stock": int(item.get("stock") or 0),
                        "min_stock": int(item.get("min_stock") or 0),
                        "sku": item.get("sku") or item["sku_generated"],
                        "unit": item.get("unit") or "pcs",
                        "hsn_code": item.get("hsn_code") or None,
                        "gst_rate": Decimal(item.get("gst_rate") or "0"),
                        "description": item.get("description") or "",
                    }
                    current_sku = str(defaults.get("sku") or "")

                    if Product.objects.filter(sku=defaults["sku"]).exclude(owner=request.user).exists():
                        # Never overwrite another tenant's SKU (sku is globally unique in current schema).
                        skipped_count += 1
                        continue

                    obj, created = Product.objects.update_or_create(
                        owner=request.user,
                        sku=defaults["sku"],
                        defaults=defaults,
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
        except IntegrityError:
            logger.exception(
                "Bulk product import failed (user=%s line=%s sku=%s)",
                int(request.user.id),
                current_line,
                current_sku,
            )
            messages.error(
                request,
                "Import failed due to invalid data in the CSV. "
                "Check that stock/min_stock are not negative, then upload again.",
            )
            return redirect(request.path)

        if desktop_stage:
            _bulk_stage_delete(kind="products", user_id=request.user.id, token=token)
        summary_parts = [f"{created_count} created"]
        if updated_count:
            summary_parts.append(f"{updated_count} updated")
        if skipped_count:
            summary_parts.append(f"{skipped_count} skipped")
        messages.success(request, f"Saved Successfully: {', '.join(summary_parts)} products.")
        return redirect("commerce:product_list")

    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and not request.POST.get("confirm"):
        if form.is_valid():
            dict_rows, read_errors = _csv_to_dict_rows(form.cleaned_data["file"])
            errors.extend(read_errors)
            preview_total = len(dict_rows)

            validated: list[dict] = []
            for row in dict_rows:
                line = row.get("_line") or "?"
                name = (row.get("name") or "").strip()
                category = (row.get("category") or "").strip()
                sku = (row.get("sku") or "").strip()
                unit = (row.get("unit") or "").strip() or "pcs"
                hsn_code = (row.get("hsn_code") or "").strip()
                description = (row.get("description") or "").strip()

                if not name:
                    errors.append(f"Line {line}: name is required.")
                    continue

                try:
                    price = _parse_decimal_field(row.get("price"), default=Decimal("0"))
                except (InvalidOperation, TypeError):
                    errors.append(f"Line {line}: price must be a number.")
                    continue
                if price < 0:
                    errors.append(f"Line {line}: price must be >= 0.")
                    continue

                try:
                    stock = _parse_int_field(row.get("stock"), default=0)
                    min_stock = _parse_int_field(row.get("min_stock"), default=0)
                except (InvalidOperation, ValueError, TypeError):
                    errors.append(f"Line {line}: stock/min_stock must be integers.")
                    continue
                if stock < 0:
                    errors.append(f"Line {line}: stock must be >= 0.")
                    continue
                if min_stock < 0:
                    errors.append(f"Line {line}: min_stock must be >= 0.")
                    continue

                try:
                    gst_rate = _parse_decimal_field(row.get("gst_rate"), default=Decimal("0"))
                except (InvalidOperation, TypeError):
                    errors.append(f"Line {line}: gst_rate must be a number.")
                    continue

                sku_generated = sku
                if not sku_generated:
                    # Deterministic per file import: NAME + line
                    sku_generated = f"SKU-{name[:10].upper().replace(' ', '')}-{line}"

                if Product.objects.filter(owner=request.user, sku=sku_generated).exists() and not sku:
                    # Avoid collisions for generated SKUs.
                    sku_generated = f"{sku_generated}-X"

                if Product.objects.filter(sku=sku_generated).exclude(owner=request.user).exists():
                    errors.append(f"Line {line}: sku already used by another account ({sku_generated}).")
                    continue

                validated.append(
                    {
                        "line": str(line),
                        "name": name,
                        "category": category,
                        "price": str(price),
                        "stock": stock,
                        "min_stock": min_stock,
                        "sku": sku or "",
                        "sku_generated": sku_generated,
                        "unit": unit,
                        "hsn_code": hsn_code,
                        "gst_rate": str(gst_rate),
                        "description": description,
                    }
                )

            if not errors:
                if _use_file_staging():
                    try:
                        bulk_token = _bulk_stage_write(kind="products", user_id=request.user.id, rows=validated)
                    except Exception:
                        errors.append("Could not prepare import. Please try again.")
                else:
                    request.session[session_key] = validated
            else:
                if not _use_file_staging():
                    request.session[session_key] = []
            preview_rows = [
                [
                    str(r.get("line") or (i + 1)),
                    r["name"],
                    r.get("category") or "-",
                    r.get("sku") or r["sku_generated"],
                    r["price"],
                    str(r.get("stock") or 0),
                    str(r.get("min_stock") or 0),
                    r.get("unit") or "pcs",
                    r.get("gst_rate") or "0",
                ]
                for i, r in enumerate(validated[:50])
            ]

    return render(
        request,
        "commerce/product_bulk_upload.html",
        {
            "form": form,
            "page_title": "Bulk Add Products",
            "page_subtitle": "Upload a CSV to create/update products (preview before import).",
            "sample_url": reverse("commerce:product_sample_csv"),
            "back_url": reverse("commerce:product_list"),
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "bulk_token": bulk_token,
            "errors": errors,
        },
    )


@login_required
def payment_sample_csv(request):
    content = "invoice_number,amount,method,reference,note\nINV-20260227-ABC123,500,cash,,Advance\n"
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="payment_sample.csv"'
    return resp


@login_required
def payment_bulk_upload(request):
    if not can_edit(request.user):
        messages.error(request, "Permission denied. (Role: view-only)")
        return redirect("commerce:payment_list")

    session_key = "kp_bulk_payment_rows"
    preview_headers = ["Line", "Invoice", "Amount", "Method", "Reference"]
    preview_rows: list[list[str]] | None = None
    preview_total: int | None = None
    errors: list[str] = []
    bulk_token: str | None = None

    if request.method == "POST" and request.POST.get("confirm"):
        desktop_stage = _use_file_staging()
        token = (request.POST.get("bulk_token") or "").strip()
        payload: list[dict] = []
        if desktop_stage:
            payload = _bulk_stage_read(kind="payments", user_id=request.user.id, token=token)
            if not payload:
                fallback_token, fallback_payload = _bulk_stage_fallback_read(
                    kind="payments",
                    user_id=request.user.id,
                    token=token,
                )
                if fallback_payload:
                    logger.warning(
                        "Bulk upload confirm missing token; using fallback (kind=%s user=%s token=%s fallback=%s)",
                        "payments",
                        int(request.user.id),
                        _token_hint(token),
                        _token_hint(fallback_token),
                    )
                    token = fallback_token
                    payload = fallback_payload
        else:
            payload = request.session.pop(session_key, None) or []
        if not payload:
            if desktop_stage:
                try:
                    pending = _bulk_stage_recent_files(kind="payments", user_id=request.user.id)
                    logger.warning(
                        "Bulk payment confirm failed (kind=%s user=%s token=%s pending_files=%s)",
                        "payments",
                        int(request.user.id),
                        _token_hint(token),
                        len(pending),
                    )
                except Exception:
                    pass
            messages.error(request, "Import failed (preview expired). Please upload the CSV again.")
            return redirect(request.path)

        created_count = 0
        with transaction.atomic():
            for item in payload:
                invoice = Invoice.objects.get(id=item["invoice_id"], order__owner=request.user)
                Payment.objects.create(
                    invoice=invoice,
                    amount=Decimal(item["amount"]),
                    method=item.get("method") or "",
                    reference=item.get("reference") or "",
                    note=item.get("note") or "",
                )
                created_count += 1

        if desktop_stage:
            _bulk_stage_delete(kind="payments", user_id=request.user.id, token=token)
        messages.success(request, f"Saved Successfully: {created_count} payments imported.")
        return redirect("commerce:payment_list")

    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and not request.POST.get("confirm"):
        if form.is_valid():
            dict_rows, read_errors = _csv_to_dict_rows(form.cleaned_data["file"])
            errors.extend(read_errors)
            preview_total = len(dict_rows)

            validated: list[dict] = []
            for row in dict_rows:
                line = row.get("_line") or "?"
                invoice_number = (row.get("invoice_number") or "").strip()
                amount_raw = (row.get("amount") or "").strip()
                method = (row.get("method") or "").strip()
                reference = (row.get("reference") or "").strip()
                note = (row.get("note") or "").strip()

                if not invoice_number:
                    errors.append(f"Line {line}: invoice_number is required.")
                    continue

                invoice = Invoice.objects.filter(order__owner=request.user, number__iexact=invoice_number).first()
                if not invoice:
                    errors.append(f"Line {line}: invoice not found ({invoice_number}).")
                    continue

                try:
                    amount = _parse_decimal_field(amount_raw)
                except (InvalidOperation, TypeError):
                    errors.append(f"Line {line}: amount must be a number.")
                    continue
                if amount <= 0:
                    errors.append(f"Line {line}: amount must be > 0.")
                    continue

                validated.append(
                    {
                        "invoice_id": invoice.id,
                        "invoice_label": invoice.number,
                        "amount": str(amount),
                        "method": method,
                        "reference": reference,
                        "note": note,
                    }
                )

            if not errors:
                if _use_file_staging():
                    try:
                        bulk_token = _bulk_stage_write(kind="payments", user_id=request.user.id, rows=validated)
                    except Exception:
                        errors.append("Could not prepare import. Please try again.")
                else:
                    request.session[session_key] = validated
            else:
                if not _use_file_staging():
                    request.session[session_key] = []
            preview_rows = [
                [str(i + 1), r["invoice_label"], r["amount"], r.get("method") or "-", r.get("reference") or "-"]
                for i, r in enumerate(validated[:50])
            ]

    return render(
        request,
        "commerce/payment_bulk_upload.html",
        {
            "form": form,
            "page_title": "Bulk Add Payments",
            "page_subtitle": "Upload a CSV to create payments (preview before import).",
            "sample_url": reverse("commerce:payment_sample_csv"),
            "back_url": reverse("commerce:payment_list"),
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "bulk_token": bulk_token,
            "errors": errors,
        },
    )
