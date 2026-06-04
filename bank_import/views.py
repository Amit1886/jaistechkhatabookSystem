from __future__ import annotations

import json
import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from bank_import.forms import BankStatementUploadForm
from bank_import.models import BankImportLog
from bank_import.statement_parser import parse_bank_statement
from bank_import.transaction_mapper import classify_bank_txn, map_bank_txn_to_entries
from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry

logger = logging.getLogger(__name__)


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        sync_settings_registry()
    except Exception:
        pass
    try:
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        value_obj = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return value_obj.value if value_obj else definition.default_value
    except Exception:
        return default


def _bank_mapping_rules() -> dict[str, Any]:
    val = _get_global_setting("bank_import_mapping", {}) or {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}


@login_required
def bank_statement_import(request):
    if not bool(_get_global_setting("bank_import_enabled", True)):
        messages.error(request, "Bank statement import is disabled by admin settings.")
        return redirect("accounts:dashboard")

    preview_headers = ["Date", "Description", "Debit", "Credit", "Balance", "Action"]
    preview_rows: list[list[str]] | None = None
    preview_total: int | None = None
    errors: list[str] = []
    bulk_token: str | None = None
    preview_note: str = ""

    mapping_rules = _bank_mapping_rules()

    if request.method == "POST" and request.POST.get("confirm"):
        token = (request.POST.get("bulk_token") or "").strip()
        try:
            log = BankImportLog.objects.filter(id=int(token), owner=request.user).first()
        except Exception:
            log = None
        if not log or not log.file:
            messages.error(request, "Import failed (preview expired). Please upload the statement again.")
            return redirect(request.path)

        try:
            log.file.open("rb")
            txns = parse_bank_statement(log.file)
        except Exception as e:
            log.status = BankImportLog.Status.FAILED
            log.error = f"{type(e).__name__}: {e}"
            log.save(update_fields=["status", "error"])
            messages.error(request, "Could not read the statement file.")
            return redirect(request.path)
        finally:
            try:
                log.file.close()
            except Exception:
                pass

        created = 0
        failed = 0
        created_types: dict[str, int] = {}
        for txn in txns:
            try:
                res = map_bank_txn_to_entries(request.user, txn, mapping_rules=mapping_rules)
                if res.ok:
                    created += 1
                    created_types[res.created_type] = created_types.get(res.created_type, 0) + 1
                else:
                    failed += 1
            except Exception:
                failed += 1
                continue

        log.status = BankImportLog.Status.IMPORTED
        log.summary = {
            "total_rows": len(txns),
            "created": created,
            "failed": failed,
            "created_types": created_types,
        }
        log.save(update_fields=["status", "summary"])
        messages.success(request, f"Saved Successfully: {created} entries imported from bank statement.")
        return redirect(request.path)

    form = BankStatementUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and not request.POST.get("confirm"):
        if form.is_valid():
            f = form.cleaned_data["file"]
            log = BankImportLog.objects.create(owner=request.user, file=f, status=BankImportLog.Status.UPLOADED)
            try:
                txns = parse_bank_statement(f)
                preview_total = len(txns)
                preview_rows = []
                for t in txns[:50]:
                    preview_rows.append(
                        [
                            t.date or "-",
                            (t.description or "")[:80],
                            str(t.debit or ""),
                            str(t.credit or ""),
                            str(t.balance or ""),
                            classify_bank_txn(t, mapping_rules=mapping_rules),
                        ]
                    )
                log.status = BankImportLog.Status.PREVIEWED
                log.summary = {"total_rows": len(txns)}
                log.save(update_fields=["status", "summary"])
                bulk_token = str(log.id)
                preview_note = "Tip: Configure mapping rules in Settings → Bank Import Mapping."
            except Exception as e:
                log.status = BankImportLog.Status.FAILED
                log.error = f"{type(e).__name__}: {e}"
                log.save(update_fields=["status", "error"])
                errors.append("Could not parse this statement. Try CSV, or install openpyxl for XLSX.")

    recent_logs = BankImportLog.objects.filter(owner=request.user).order_by("-created_at")[:20]
    return render(
        request,
        "bank_import/import_statement.html",
        {
            "form": form,
            "page_title": "Import Bank Statement",
            "page_subtitle": "Upload a CSV/XLSX, preview mapping, then import entries.",
            "back_url": reverse("accounts:dashboard"),
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "preview_total": preview_total,
            "preview_note": preview_note,
            "bulk_token": bulk_token,
            "errors": errors,
            "recent_logs": recent_logs,
        },
    )
