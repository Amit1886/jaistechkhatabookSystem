from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.utils import render_to_pdf_bytes
from billing.services import user_has_feature
from accounts.roles import can_delete as erp_can_delete, can_edit as erp_can_edit
from ledger.forms import (
    JournalVoucherForm,
    JournalVoucherLineFormSet,
    ReturnNoteForm,
    ReturnNoteItemFormSet,
    StockTransferForm,
    StockTransferItemFormSet,
)
from ledger.models import JournalVoucher, LedgerAccount, ReturnNote, StockTransfer
from ledger.services.receipts import build_receipt_context


@login_required
def universal_receipt(request):
    reference_type = (request.GET.get("reference_type") or "").strip()
    reference_id_raw = (request.GET.get("reference_id") or "").strip()
    voucher_type = (request.GET.get("voucher_type") or "").strip()
    kind = (request.GET.get("kind") or "").strip()
    fmt = (request.GET.get("format") or "").strip().lower()

    try:
        reference_id = int(reference_id_raw)
    except Exception:
        reference_id = None

    if not reference_type or not reference_id:
        raise Http404("Missing receipt reference.")

    context = build_receipt_context(
        owner=request.user,
        reference_type=reference_type,
        reference_id=reference_id,
        voucher_type=voucher_type or None,
        kind=kind or None,
    )
    if not context:
        raise Http404("Receipt not available for this document.")

    context["hide_sidebar"] = True
    context["pdf_url"] = f"/ledger/receipt/?reference_type={reference_type}&reference_id={reference_id}&voucher_type={voucher_type}&format=pdf"

    if fmt == "pdf":
        pdf_bytes = render_to_pdf_bytes("ledger/receipt_pdf.html", context, request=request)
        if not pdf_bytes:
            return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

        filename = f"receipt_{context.get('reference_no') or reference_id}.pdf"
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        inline = (request.GET.get("inline") or "").strip() == "1"
        resp["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{filename}"'
        return resp

    return render(request, "ledger/receipt.html", context)


@login_required
def stock_transfer_list(request):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()

    qs = StockTransfer.objects.select_related("from_warehouse", "to_warehouse").filter(owner=request.user)
    if q:
        qs = qs.filter(notes__icontains=q)
    if status in {s for s, _ in StockTransfer.Status.choices}:
        qs = qs.filter(status=status)

    qs = qs.order_by("-date", "-id")
    return render(request, "ledger/stock_transfer_list.html", {"transfers": qs, "q": q, "status": status})


@login_required
def stock_transfer_create(request):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot create stock transfers.")
        return redirect("ledger:stock_transfer_list")

    transfer = StockTransfer(owner=request.user)
    if request.method == "POST":
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            transfer = form.save(commit=False)
            transfer.owner = request.user
            # Always create as draft first; posting handled separately.
            if transfer.status == StockTransfer.Status.POSTED:
                transfer.status = StockTransfer.Status.DRAFT
            transfer.save()
            formset.save()
            messages.success(request, "Saved Successfully")
            return redirect("ledger:stock_transfer_detail", pk=transfer.id)
    else:
        form = StockTransferForm(instance=transfer, initial={"status": StockTransfer.Status.DRAFT})
        formset = StockTransferItemFormSet(instance=transfer)

    return render(request, "ledger/stock_transfer_form.html", {"form": form, "formset": formset, "transfer": transfer})


@login_required
def stock_transfer_detail(request, pk: int):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})

    transfer = get_object_or_404(
        StockTransfer.objects.select_related("from_warehouse", "to_warehouse").prefetch_related("items", "items__product"),
        id=pk,
        owner=request.user,
    )
    return render(request, "ledger/stock_transfer_detail.html", {"transfer": transfer})


@login_required
def stock_transfer_edit(request, pk: int):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit stock transfers.")
        return redirect("ledger:stock_transfer_list")

    transfer = get_object_or_404(StockTransfer, id=pk, owner=request.user)
    if transfer.status != StockTransfer.Status.DRAFT:
        messages.warning(request, "Only Draft transfers can be edited.")
        return redirect("ledger:stock_transfer_detail", pk=transfer.id)

    if request.method == "POST":
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            updated = form.save(commit=False)
            updated.owner = request.user
            updated.status = StockTransfer.Status.DRAFT
            updated.save()
            formset.save()
            messages.success(request, "Saved Successfully")
            return redirect("ledger:stock_transfer_detail", pk=transfer.id)
    else:
        form = StockTransferForm(instance=transfer)
        formset = StockTransferItemFormSet(instance=transfer)

    return render(request, "ledger/stock_transfer_form.html", {"form": form, "formset": formset, "transfer": transfer})


@login_required
@require_POST
def stock_transfer_post(request, pk: int):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot post stock transfers.")
        return redirect("ledger:stock_transfer_detail", pk=pk)

    transfer = get_object_or_404(StockTransfer, id=pk, owner=request.user)
    if transfer.status != StockTransfer.Status.DRAFT:
        return redirect("ledger:stock_transfer_detail", pk=transfer.id)

    if not transfer.items.exists():
        messages.error(request, "Add at least one item before posting.")
        return redirect("ledger:stock_transfer_edit", pk=transfer.id)

    transfer.status = StockTransfer.Status.POSTED
    transfer.save(update_fields=["status"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:stock_transfer_detail", pk=transfer.id)


@login_required
@require_POST
def stock_transfer_cancel(request, pk: int):
    if not user_has_feature(request.user, "inventory.stock_transfer"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Stock Transfer"})
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can cancel stock transfers.")
        return redirect("ledger:stock_transfer_detail", pk=pk)

    transfer = get_object_or_404(StockTransfer, id=pk, owner=request.user)
    transfer.status = StockTransfer.Status.CANCELLED
    transfer.save(update_fields=["status"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:stock_transfer_detail", pk=transfer.id)


@login_required
def journal_voucher_list(request):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})

    qs = JournalVoucher.objects.filter(owner=request.user).order_by("-date", "-id")
    return render(request, "ledger/journal_voucher_list.html", {"vouchers": qs})


@login_required
def journal_voucher_create(request):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot create journal vouchers.")
        return redirect("ledger:journal_voucher_list")

    voucher = JournalVoucher(owner=request.user)
    if request.method == "POST":
        form = JournalVoucherForm(request.POST, instance=voucher)
        formset = JournalVoucherLineFormSet(request.POST, instance=voucher)
        if form.is_valid() and formset.is_valid():
            voucher = form.save(commit=False)
            voucher.owner = request.user
            if voucher.status == JournalVoucher.Status.POSTED:
                voucher.status = JournalVoucher.Status.DRAFT
            voucher.save()
            formset.save()
            messages.success(request, "Saved Successfully")
            return redirect("ledger:journal_voucher_detail", pk=voucher.id)
    else:
        form = JournalVoucherForm(instance=voucher, initial={"status": JournalVoucher.Status.DRAFT})
        formset = JournalVoucherLineFormSet(instance=voucher)

    return render(request, "ledger/journal_voucher_form.html", {"form": form, "formset": formset, "voucher": voucher})


@login_required
def journal_voucher_detail(request, pk: int):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})

    voucher = get_object_or_404(
        JournalVoucher.objects.prefetch_related("lines", "lines__account", "lines__party"),
        id=pk,
        owner=request.user,
    )
    return render(request, "ledger/journal_voucher_detail.html", {"voucher": voucher})


@login_required
def journal_voucher_edit(request, pk: int):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit journal vouchers.")
        return redirect("ledger:journal_voucher_list")

    voucher = get_object_or_404(JournalVoucher, id=pk, owner=request.user)
    if voucher.status != JournalVoucher.Status.DRAFT:
        messages.warning(request, "Only Draft vouchers can be edited.")
        return redirect("ledger:journal_voucher_detail", pk=voucher.id)

    if request.method == "POST":
        form = JournalVoucherForm(request.POST, instance=voucher)
        formset = JournalVoucherLineFormSet(request.POST, instance=voucher)
        if form.is_valid() and formset.is_valid():
            updated = form.save(commit=False)
            updated.owner = request.user
            updated.status = JournalVoucher.Status.DRAFT
            updated.save()
            formset.save()
            messages.success(request, "Saved Successfully")
            return redirect("ledger:journal_voucher_detail", pk=voucher.id)
    else:
        form = JournalVoucherForm(instance=voucher)
        formset = JournalVoucherLineFormSet(instance=voucher)

    return render(request, "ledger/journal_voucher_form.html", {"form": form, "formset": formset, "voucher": voucher})


@login_required
@require_POST
def journal_voucher_post(request, pk: int):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot post journal vouchers.")
        return redirect("ledger:journal_voucher_detail", pk=pk)

    voucher = get_object_or_404(JournalVoucher, id=pk, owner=request.user)
    if voucher.status != JournalVoucher.Status.DRAFT:
        return redirect("ledger:journal_voucher_detail", pk=voucher.id)

    lines = list(voucher.lines.all())
    if not lines:
        messages.error(request, "Add at least one line before posting.")
        return redirect("ledger:journal_voucher_edit", pk=voucher.id)

    # Basic balance validation
    debit_total = sum((l.debit or 0) for l in lines)
    credit_total = sum((l.credit or 0) for l in lines)
    if debit_total != credit_total:
        messages.error(request, "Voucher must be balanced (total debit must equal total credit).")
        return redirect("ledger:journal_voucher_detail", pk=voucher.id)

    voucher.status = JournalVoucher.Status.POSTED
    voucher.save(update_fields=["status"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:journal_voucher_detail", pk=voucher.id)


@login_required
@require_POST
def journal_voucher_cancel(request, pk: int):
    if not user_has_feature(request.user, "accounting.journal_vouchers"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Journal Vouchers"})
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can cancel journal vouchers.")
        return redirect("ledger:journal_voucher_detail", pk=pk)

    voucher = get_object_or_404(JournalVoucher, id=pk, owner=request.user)
    voucher.status = JournalVoucher.Status.CANCELLED
    voucher.save(update_fields=["status"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:journal_voucher_detail", pk=voucher.id)


@login_required
def credit_note_list(request):
    if not user_has_feature(request.user, "billing.credit_notes"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes"})
    qs = ReturnNote.objects.select_related("invoice", "invoice__order", "invoice__order__party").filter(
        owner=request.user, note_type=ReturnNote.NoteType.CREDIT
    ).order_by("-date", "-id")
    return render(request, "ledger/return_note_list.html", {"notes": qs, "note_label": "Credit Notes"})


@login_required
def debit_note_list(request):
    if not user_has_feature(request.user, "billing.debit_notes"):
        return render(request, "core/upgrade_required.html", {"feature_name": "Debit Notes"})
    qs = ReturnNote.objects.select_related("invoice", "invoice__order", "invoice__order__party").filter(
        owner=request.user, note_type=ReturnNote.NoteType.DEBIT
    ).order_by("-date", "-id")
    return render(request, "ledger/return_note_list.html", {"notes": qs, "note_label": "Debit Notes"})


@login_required
def return_note_create(request, note_type: str):
    is_credit = (note_type or "").lower() == ReturnNote.NoteType.CREDIT
    feature_key = "billing.credit_notes" if is_credit else "billing.debit_notes"
    if not user_has_feature(request.user, feature_key):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes" if is_credit else "Debit Notes"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot create notes.")
        return redirect("ledger:credit_note_list" if is_credit else "ledger:debit_note_list")

    note = ReturnNote(owner=request.user, note_type=ReturnNote.NoteType.CREDIT if is_credit else ReturnNote.NoteType.DEBIT)

    if request.method == "POST":
        form = ReturnNoteForm(request.POST, instance=note)
        formset = ReturnNoteItemFormSet(request.POST, instance=note)
        if form.is_valid() and formset.is_valid():
            note = form.save(commit=False)
            note.owner = request.user
            note.note_type = ReturnNote.NoteType.CREDIT if is_credit else ReturnNote.NoteType.DEBIT
            note.status = ReturnNote.Status.DRAFT
            note.save()
            formset.save()
            note.compute_totals()
            note.save(update_fields=["taxable_amount", "tax_amount", "total_amount"])
            messages.success(request, "Saved Successfully")
            return redirect("ledger:return_note_detail", pk=note.id)
    else:
        # Filter invoice choices by sales/purchase
        invoice_qs = None
        try:
            from commerce.models import Invoice
            if is_credit:
                invoice_qs = Invoice.objects.select_related("order", "order__party").filter(order__owner=request.user, order__order_type="SALE")
            else:
                invoice_qs = Invoice.objects.select_related("order", "order__party").filter(order__owner=request.user, order__order_type="PURCHASE")
        except Exception:
            invoice_qs = None
        form = ReturnNoteForm(instance=note)
        if invoice_qs is not None:
            form.fields["invoice"].queryset = invoice_qs.order_by("-created_at", "-id")
        formset = ReturnNoteItemFormSet(instance=note)

    return render(
        request,
        "ledger/return_note_form.html",
        {"form": form, "formset": formset, "note": note, "note_label": "Credit Note" if is_credit else "Debit Note"},
    )


@login_required
def return_note_detail(request, pk: int):
    note = get_object_or_404(
        ReturnNote.objects.select_related("invoice", "invoice__order", "invoice__order__party").prefetch_related("items", "items__product"),
        id=pk,
        owner=request.user,
    )
    feature_key = "billing.credit_notes" if note.note_type == ReturnNote.NoteType.CREDIT else "billing.debit_notes"
    if not user_has_feature(request.user, feature_key):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes" if note.note_type == ReturnNote.NoteType.CREDIT else "Debit Notes"})

    return render(request, "ledger/return_note_detail.html", {"note": note})


@login_required
def return_note_edit(request, pk: int):
    note = get_object_or_404(ReturnNote, id=pk, owner=request.user)
    feature_key = "billing.credit_notes" if note.note_type == ReturnNote.NoteType.CREDIT else "billing.debit_notes"
    if not user_has_feature(request.user, feature_key):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes" if note.note_type == ReturnNote.NoteType.CREDIT else "Debit Notes"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit notes.")
        return redirect("ledger:return_note_detail", pk=note.id)
    if note.status != ReturnNote.Status.DRAFT:
        messages.warning(request, "Only Draft notes can be edited.")
        return redirect("ledger:return_note_detail", pk=note.id)

    if request.method == "POST":
        form = ReturnNoteForm(request.POST, instance=note)
        formset = ReturnNoteItemFormSet(request.POST, instance=note)
        if form.is_valid() and formset.is_valid():
            note = form.save(commit=False)
            note.owner = request.user
            note.status = ReturnNote.Status.DRAFT
            note.save()
            formset.save()
            note.compute_totals()
            note.save(update_fields=["taxable_amount", "tax_amount", "total_amount"])
            messages.success(request, "Saved Successfully")
            return redirect("ledger:return_note_detail", pk=note.id)
    else:
        form = ReturnNoteForm(instance=note)
        # Don't allow switching invoice on edit to avoid posting confusion
        form.fields["invoice"].disabled = True
        formset = ReturnNoteItemFormSet(instance=note)

    return render(request, "ledger/return_note_form.html", {"form": form, "formset": formset, "note": note, "note_label": "Return Note"})


@login_required
@require_POST
def return_note_post(request, pk: int):
    note = get_object_or_404(ReturnNote, id=pk, owner=request.user)
    feature_key = "billing.credit_notes" if note.note_type == ReturnNote.NoteType.CREDIT else "billing.debit_notes"
    if not user_has_feature(request.user, feature_key):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes" if note.note_type == ReturnNote.NoteType.CREDIT else "Debit Notes"})
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot post notes.")
        return redirect("ledger:return_note_detail", pk=note.id)

    if note.status != ReturnNote.Status.DRAFT:
        return redirect("ledger:return_note_detail", pk=note.id)
    if not note.items.exists():
        messages.error(request, "Add at least one item before posting.")
        return redirect("ledger:return_note_edit", pk=note.id)

    note.compute_totals()
    note.status = ReturnNote.Status.POSTED
    note.save(update_fields=["status", "taxable_amount", "tax_amount", "total_amount"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:return_note_detail", pk=note.id)


@login_required
@require_POST
def return_note_cancel(request, pk: int):
    note = get_object_or_404(ReturnNote, id=pk, owner=request.user)
    feature_key = "billing.credit_notes" if note.note_type == ReturnNote.NoteType.CREDIT else "billing.debit_notes"
    if not user_has_feature(request.user, feature_key):
        return render(request, "core/upgrade_required.html", {"feature_name": "Credit Notes" if note.note_type == ReturnNote.NoteType.CREDIT else "Debit Notes"})
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can cancel notes.")
        return redirect("ledger:return_note_detail", pk=note.id)

    note.status = ReturnNote.Status.CANCELLED
    note.save(update_fields=["status"])
    messages.success(request, "Saved Successfully")
    return redirect("ledger:return_note_detail", pk=note.id)
