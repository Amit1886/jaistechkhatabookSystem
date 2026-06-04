# ~/khata_pro/commerce/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import modelformset_factory
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.db.models import Q, F, Sum, Count, DecimalField, ExpressionWrapper
from django.db.utils import OperationalError, ProgrammingError
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
import json
import random
import string
import os
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.urls import reverse

from .models import (
    Category,
    Product,
    Warehouse,
    Order,
    OrderItem,
    Quotation,
    QuotationItem,
    QuotationAuditLog,
    Invoice,
    SalesVoucher,
    SalesVoucherItem,
    Payment,
    Stock,
    ChatThread,
    ChatMessage,
    Coupon,
    UserCoupon,
    CouponUsage,
    WhatsAppOrderInbox,
)
from khataapp.models import UserProfile
from django.db import transaction
from .forms import (
    WarehouseForm,
    SalesVoucherForm,
    SalesVoucherItemForm,
    BaseSalesVoucherItemFormSet,
)
from .forms import OrderForm, OrderItemFormSet
from decimal import Decimal
from accounts.roles import can_delete as erp_can_delete, can_edit as erp_can_edit
from khataapp.models import Party
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

from commerce.services import build_reorder_plan, build_reorder_summary
from commerce.services.whatsapp_conversation import handle_whatsapp_order_message
from accounts.utils import render_to_pdf_bytes

User = get_user_model()

def _order_access_q(user):
    """
    Orders visible to the current user.

    - Normal users: their own orders OR legacy rows where owner is null but party.owner is them.
    - Staff/superuser: all orders.
    """
    try:
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return Q()
    except Exception:
        pass
    return Q(owner=user) | Q(owner__isnull=True, party__owner=user)



def generate_unique_sku():
    """Generate a unique SKU code"""
    while True:
        sku = 'SKU' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Product.objects.filter(sku=sku).exists():
            return sku

@login_required
def _download_invoice_reportlab(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = OrderItem.objects.filter(order=order)

    # Create a buffer for PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20, leftMargin=20,
                            topMargin=20, bottomMargin=20)

    elements = []
    styles = getSampleStyleSheet()

    # ✅ Logo and Company Header
    company_name = "KhataPro Commerce"
    tagline = "Smart Accounting & Inventory System"
    logo_path = "/home/Khataapp/myproject/khatapro/static/images/logo.png"  # Change if needed

    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=60, height=60))
    elements.append(Paragraph(f"<b style='font-size:18px;color:#004aad'>{company_name}</b>", styles['Title']))
    elements.append(Paragraph(f"<font color='#0073e6'>{tagline}</font>", styles['Normal']))
    elements.append(Spacer(1, 12))

    # ✅ Blue Header Bar
    data = [[f"<b>INVOICE #{order.id}</b>", f"<b>Date:</b> {order.created_at.strftime('%d-%m-%Y')}"]]
    table = Table(data, colWidths=[250, 250])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0073e6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # ✅ Party Details
    elements.append(Paragraph(f"<b>Order ID:</b> {order.id}", styles['Normal']))
    elements.append(Paragraph(f"<b>Owner:</b> {(order.owner.email if order.owner else '-')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Placed by:</b> {order.placed_by}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {order.created_at.strftime('%d %b %Y, %I:%M %p')}", styles['Normal']))


    # ✅ Table Header
    table_data = [["Product", "Qty", "Price", "Subtotal"]]
    for item in items:
        product_name = "-"
        if getattr(item, "product", None):
            product_name = item.product.name
        elif getattr(item, "raw_name", None):
            product_name = item.raw_name
        line_total = item.line_total()
        table_data.append([
            product_name,
            f"{item.qty}",
            f"₹ {item.price:.2f}",
            f"₹ {line_total:.2f}"
        ])

    # ✅ Totals
    subtotal = order.subtotal_amount()
    discount = order.discount_amount or Decimal("0.00")
    tax = order.tax_amount or Decimal("0.00")
    sundry = order.bill_sundry_total()
    total = order.total_amount()
    table_data.append(["", "", "Subtotal:", f"₹ {subtotal:.2f}"])
    table_data.append(["", "", "Discount:", f"₹ {discount:.2f}"])
    table_data.append(["", "", "Tax:", f"₹ {tax:.2f}"])
    if sundry != Decimal("0.00"):
        table_data.append(["", "", "Bill Sundry:", f"₹ {sundry:.2f}"])
    table_data.append(["", "", "Total:", f"₹ {total:.2f}"])

    # ✅ Create item table
    t = Table(table_data, colWidths=[200, 80, 100, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#004aad")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -2), colors.whitesmoke),
        ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # ✅ Footer Message
    elements.append(Paragraph(
        "<b>Thank you for your business!</b><br/>This is a computer-generated invoice.",
        styles['Normal']
    ))

    # Build the PDF
    doc.build(elements)

    # Return as response
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{order.id}.pdf"'
    response.write(pdf)
    return response


@login_required
def download_invoice(request, order_id):
    """
    Professional, consistent PDF export for an Order (used by /commerce/download-invoice/<id>/).
    Uses the same xhtml2pdf pipeline as other documents so it matches invoice/voucher/receipt style.
    """
    order = get_object_or_404(
        Order.objects.select_related("party").prefetch_related("items", "items__product").filter(_order_access_q(request.user)),
        id=order_id,
    )
    items = order.items.select_related("product").all().order_by("id")

    try:
        invoice = getattr(order, "invoice", None)
    except Exception:
        invoice = None

    subtotal = order.subtotal_amount()
    discount = getattr(order, "discount_amount", None) or Decimal("0.00")
    sundry = order.bill_sundry_total()
    tax = getattr(order, "tax_amount", None) or Decimal("0.00")
    total = order.total_amount()

    is_gst = bool(
        invoice
        and (getattr(invoice, "gst_type", "") or "").upper() == "GST"
        and (getattr(order, "tax_percent", Decimal("0.00")) or Decimal("0.00")) > 0
    )
    cgst = sgst = igst = Decimal("0.00")
    if is_gst:
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"))
        sgst = tax - cgst

    context = {
        "order": order,
        "party": order.party,
        "invoice": invoice,
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
        "issuer": _get_issuer_profile(request.user),
    }

    pdf_bytes = render_to_pdf_bytes("commerce/order_pdf.html", context, request=request)
    if not pdf_bytes:
        return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

    filename = f"order_{order.id}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    inline = (request.GET.get("inline") or "").strip() == "1"
    resp["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{filename}"'
    return resp

# ---------------- Utility ----------------
def is_paid_user(user):
    """Check if the user's plan allows Commerce access"""
    try:
        profile = UserProfile.objects.get(user=user)
        if profile.plan and profile.plan.name.lower() in ["basic", "premium", "pro"]:
            return True
        if hasattr(profile, "has_feature") and profile.has_feature("allow_commerce"):
            return True
    except Exception:
        pass
    return False


# ---------------- Quotations ----------------
class QuotationCreateView(LoginRequiredMixin, View):
    template_name = "commerce/quotation_create.html"

    def _base_context(self, request, *, quotation=None, initial_party_id: str = ""):
        parties = Party.objects.filter(owner=request.user).order_by("name")
        products = Product.objects.filter(owner=request.user).order_by("name")
        warehouses = Warehouse.objects.all().order_by("name")
        return {
            "quotation": quotation,
            "parties": parties,
            "products": products,
            "warehouses": warehouses,
            "initial_party_id": initial_party_id,
            "initial_gst_enabled": True,
            "initial_gst_rate": "0",
        }

    def get(self, request, *args, **kwargs):
        try:
            initial_party_id = (request.GET.get("party") or "").strip()
            return render(request, self.template_name, self._base_context(request, initial_party_id=initial_party_id))
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            # Touch the table early so we can show a friendly error if migrations aren't applied.
            Quotation.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")
        submit_action = (request.POST.get("submit_action") or "").strip().lower()
        party_id = (request.POST.get("party") or "").strip()
        warehouse_id = (request.POST.get("warehouse") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()

        date_raw = (request.POST.get("quotation_date") or request.POST.get("order_date") or "").strip()
        valid_till_raw = (request.POST.get("valid_till") or "").strip()

        try:
            q_date = timezone.localdate()
            if date_raw:
                q_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except Exception:
            q_date = timezone.localdate()

        try:
            valid_till = None
            if valid_till_raw:
                valid_till = datetime.strptime(valid_till_raw, "%Y-%m-%d").date()
        except Exception:
            valid_till = None
        if valid_till and valid_till < q_date:
            messages.error(request, "Valid till cannot be before quotation date.")
            return redirect("commerce:quotation_create")

        if not party_id:
            messages.error(request, "Please select a party.")
            return redirect("commerce:quotation_create")

        party = Party.objects.filter(id=party_id, owner=request.user).first()
        if not party:
            messages.error(request, "Invalid party selected.")
            return redirect("commerce:quotation_create")

        warehouse = None
        if warehouse_id:
            warehouse = Warehouse.objects.filter(id=warehouse_id).first()

        gst_enabled = str(request.POST.get("gst_enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
        gst_rate_raw = (request.POST.get("gst_rate") or "").strip()
        try:
            tax_percent = Decimal(gst_rate_raw or "0").quantize(Decimal("0.01")) if gst_enabled else Decimal("0.00")
        except Exception:
            tax_percent = Decimal("0.00")

        products = request.POST.getlist("product[]")
        qtys = request.POST.getlist("qty[]")
        rates = request.POST.getlist("price[]")
        row_discount_pcts = request.POST.getlist("discount_percent[]")
        row_discount_amts = request.POST.getlist("discount_amount[]")

        status = Quotation.Status.DRAFT
        if submit_action in {"send", "sent"}:
            status = Quotation.Status.SENT
        elif submit_action in {"approve", "approved"}:
            # Create-and-approve does: Draft -> Sent -> Verified -> Approved (audit logged).
            status = Quotation.Status.APPROVED

        quotation = Quotation.objects.create(
            party=party,
            date=q_date,
            valid_till=valid_till,
            status=Quotation.Status.DRAFT,
            remarks=remarks,
            created_by=request.user,
            warehouse=warehouse,
            total_amount=Decimal("0.00"),
        )
        QuotationAuditLog.objects.create(
            quotation=quotation,
            action="create",
            from_status="",
            to_status=Quotation.Status.DRAFT,
            performed_by=request.user,
            note="Created",
        )

        product_ids = []
        for p in products:
            p = (p or "").strip()
            if not p:
                continue
            try:
                product_ids.append(int(p))
            except Exception:
                continue

        allowed_products = {p.id for p in Product.objects.filter(owner=request.user, id__in=product_ids)}

        any_item = False
        total_amount = Decimal("0.00")

        for idx, (p, q, r) in enumerate(zip(products, qtys, rates)):
            p = (p or "").strip()
            q = (q or "").strip()
            r = (r or "").strip()
            if not (p and q and r):
                continue

            try:
                pid = int(p)
            except Exception:
                continue
            if pid not in allowed_products:
                continue

            try:
                qty_val = Decimal(q).quantize(Decimal("0.01"))
            except Exception:
                continue
            if qty_val <= 0:
                continue

            try:
                rate_val = Decimal(r).quantize(Decimal("0.01"))
            except Exception:
                rate_val = Decimal("0.00")
            if rate_val < 0:
                rate_val = Decimal("0.00")

            # Discount: percent OR flat, like the PC busy grid.
            try:
                dp = Decimal((row_discount_pcts[idx] if idx < len(row_discount_pcts) else "0") or "0").quantize(
                    Decimal("0.01")
                )
            except Exception:
                dp = Decimal("0.00")
            try:
                da = Decimal((row_discount_amts[idx] if idx < len(row_discount_amts) else "0") or "0").quantize(
                    Decimal("0.01")
                )
            except Exception:
                da = Decimal("0.00")
            if dp < 0:
                dp = Decimal("0.00")
            if da < 0:
                da = Decimal("0.00")

            base = qty_val * rate_val
            disc = Decimal("0.00")
            if dp > 0:
                disc = (base * dp) / Decimal("100")
            if da > 0:
                disc = da
            if disc > base:
                disc = base
            net = base - disc
            if net < 0:
                net = Decimal("0.00")

            tax_amount = (net * tax_percent) / Decimal("100") if tax_percent > 0 else Decimal("0.00")
            line_total = (net + tax_amount).quantize(Decimal("0.01"))
            total_amount += line_total
            any_item = True

            QuotationItem.objects.create(
                quotation=quotation,
                product_id=pid,
                qty=qty_val,
                rate=rate_val,
                tax=tax_percent,
                discount=disc.quantize(Decimal("0.01")),
                warehouse=warehouse,
                total=line_total,
            )

        if not any_item:
            quotation.delete()
            messages.error(request, "Quotation must contain at least one item.")
            return redirect("commerce:quotation_create")

        quotation.total_amount = total_amount
        quotation.status = status
        quotation.save(update_fields=["total_amount", "status"])

        if status == Quotation.Status.SENT:
            QuotationAuditLog.objects.create(
                quotation=quotation,
                action="send",
                from_status=Quotation.Status.DRAFT,
                to_status=Quotation.Status.SENT,
                performed_by=request.user,
                note="Sent",
            )
        elif status == Quotation.Status.APPROVED:
            QuotationAuditLog.objects.create(
                quotation=quotation,
                action="send",
                from_status=Quotation.Status.DRAFT,
                to_status=Quotation.Status.SENT,
                performed_by=request.user,
                note="Auto Sent",
            )
            QuotationAuditLog.objects.create(
                quotation=quotation,
                action="verify",
                from_status=Quotation.Status.SENT,
                to_status=Quotation.Status.VERIFIED,
                performed_by=request.user,
                note="Auto Verified",
            )
            QuotationAuditLog.objects.create(
                quotation=quotation,
                action="approve",
                from_status=Quotation.Status.VERIFIED,
                to_status=Quotation.Status.APPROVED,
                performed_by=request.user,
                note="Approved",
            )

        messages.success(request, f"Quotation {quotation.quotation_number or '#' + str(quotation.id)} saved.")
        return redirect("commerce:quotation_detail", pk=quotation.id)


class QuotationListView(LoginRequiredMixin, View):
    template_name = "commerce/quotation_list.html"

    def get(self, request, *args, **kwargs):
        try:
            Quotation.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")
        q = (request.GET.get("q") or "").strip()
        status = (request.GET.get("status") or "").strip().lower()
        date_from = parse_date(request.GET.get("from") or "")
        date_to = parse_date(request.GET.get("to") or "")

        qs = (
            Quotation.objects.filter(party__owner=request.user)
            .select_related("party", "created_by", "warehouse", "converted_order")
            .order_by("-created_at", "-id")
        )
        if q:
            qs = qs.filter(Q(quotation_number__icontains=q) | Q(party__name__icontains=q) | Q(remarks__icontains=q))
        if status:
            qs = qs.filter(status__iexact=status)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        paginator = Paginator(qs, 15)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        context = {
            "quotations": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
            "today": timezone.localdate(),
        }

        if request.GET.get("ajax") == "1":
            rows_html = render_to_string("commerce/partials/quotation_list_rows.html", context, request=request)
            pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
            return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

        return render(request, self.template_name, context)


class QuotationDetailView(LoginRequiredMixin, View):
    template_name = "commerce/quotation_detail.html"

    def get(self, request, pk: int, *args, **kwargs):
        try:
            Quotation.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")
        quotation = get_object_or_404(
            Quotation.objects.select_related("party", "warehouse", "created_by", "converted_order").prefetch_related(
                "items__product", "audit_logs"
            ),
            id=pk,
            party__owner=request.user,
        )
        return render(request, self.template_name, {"quotation": quotation})


class QuotationUpdateView(LoginRequiredMixin, View):
    template_name = "commerce/quotation_create.html"

    def get(self, request, pk: int, *args, **kwargs):
        try:
            Quotation.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")
        quotation = get_object_or_404(
            Quotation.objects.select_related("party", "warehouse", "created_by").prefetch_related("items__product"),
            id=pk,
            party__owner=request.user,
        )
        if (quotation.status or "").lower() == Quotation.Status.CONVERTED:
            messages.error(request, "Converted quotation cannot be edited.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        if (quotation.status or "").lower() in {Quotation.Status.VERIFIED, Quotation.Status.APPROVED}:
            messages.error(request, "Verified/Approved quotation cannot be edited. Reject and recreate if needed.")
            return redirect("commerce:quotation_detail", pk=quotation.id)

        parties = Party.objects.filter(owner=request.user).order_by("name")
        products = Product.objects.filter(owner=request.user).order_by("name")
        warehouses = Warehouse.objects.all().order_by("name")
        initial_items = [
            {
                "product_id": it.product_id,
                "product_name": it.product.name,
                "qty": it.qty,
                "rate": it.rate,
                "discount": it.discount,
            }
            for it in quotation.items.all()
        ]
        initial_gst_rate = "0"
        initial_gst_enabled = True
        try:
            first = quotation.items.all().first()
            if first and first.tax is not None:
                initial_gst_rate = str(Decimal(str(first.tax)).quantize(Decimal("0.01")))
        except Exception:
            initial_gst_rate = "0"
        try:
            initial_gst_enabled = Decimal(initial_gst_rate or "0") > 0
        except Exception:
            initial_gst_enabled = True
        return render(
            request,
            self.template_name,
            {
                "quotation": quotation,
                "parties": parties,
                "products": products,
                "warehouses": warehouses,
                "initial_party_id": str(quotation.party_id),
                "initial_items": initial_items,
                "initial_gst_rate": initial_gst_rate,
                "initial_gst_enabled": initial_gst_enabled,
            },
        )

    @transaction.atomic
    def post(self, request, pk: int, *args, **kwargs):
        try:
            Quotation.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Quotation module database tables are missing. Please run migrations.")
            return redirect("accounts:dashboard")
        quotation = (
            Quotation.objects.select_for_update()
            .select_related("party", "warehouse")
            .prefetch_related("items")
            .filter(id=pk, party__owner=request.user)
            .first()
        )
        if not quotation:
            messages.error(request, "Quotation not found.")
            return redirect("commerce:quotation_list")

        if (quotation.status or "").lower() == Quotation.Status.CONVERTED:
            messages.error(request, "Converted quotation cannot be edited.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        if (quotation.status or "").lower() in {Quotation.Status.VERIFIED, Quotation.Status.APPROVED}:
            messages.error(request, "Verified/Approved quotation cannot be edited.")
            return redirect("commerce:quotation_detail", pk=quotation.id)

        submit_action = (request.POST.get("submit_action") or "").strip().lower()
        warehouse_id = (request.POST.get("warehouse") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()

        date_raw = (request.POST.get("quotation_date") or request.POST.get("order_date") or "").strip()
        valid_till_raw = (request.POST.get("valid_till") or "").strip()

        try:
            q_date = quotation.date
            if date_raw:
                q_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except Exception:
            q_date = quotation.date

        try:
            valid_till = quotation.valid_till
            if valid_till_raw:
                valid_till = datetime.strptime(valid_till_raw, "%Y-%m-%d").date()
        except Exception:
            valid_till = quotation.valid_till
        if valid_till and valid_till < q_date:
            messages.error(request, "Valid till cannot be before quotation date.")
            return redirect("commerce:quotation_edit", pk=quotation.id)

        warehouse = None
        if warehouse_id:
            warehouse = Warehouse.objects.filter(id=warehouse_id).first()

        gst_enabled = str(request.POST.get("gst_enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
        gst_rate_raw = (request.POST.get("gst_rate") or "").strip()
        try:
            tax_percent = Decimal(gst_rate_raw or "0").quantize(Decimal("0.01")) if gst_enabled else Decimal("0.00")
        except Exception:
            tax_percent = Decimal("0.00")

        from_status = quotation.status
        status = quotation.status
        if submit_action in {"send", "sent"}:
            status = Quotation.Status.SENT
        elif submit_action in {"draft"}:
            status = Quotation.Status.DRAFT

        products = request.POST.getlist("product[]")
        qtys = request.POST.getlist("qty[]")
        rates = request.POST.getlist("price[]")
        row_discount_pcts = request.POST.getlist("discount_percent[]")
        row_discount_amts = request.POST.getlist("discount_amount[]")

        product_ids = []
        for p in products:
            p = (p or "").strip()
            if not p:
                continue
            try:
                product_ids.append(int(p))
            except Exception:
                continue
        allowed_products = {p.id for p in Product.objects.filter(owner=request.user, id__in=product_ids)}

        # Replace items (simple and predictable).
        QuotationItem.objects.filter(quotation=quotation).delete()
        any_item = False
        total_amount = Decimal("0.00")

        for idx, (p, q, r) in enumerate(zip(products, qtys, rates)):
            p = (p or "").strip()
            q = (q or "").strip()
            r = (r or "").strip()
            if not (p and q and r):
                continue

            try:
                pid = int(p)
            except Exception:
                continue
            if pid not in allowed_products:
                continue

            try:
                qty_val = Decimal(q).quantize(Decimal("0.01"))
            except Exception:
                continue
            if qty_val <= 0:
                continue

            try:
                rate_val = Decimal(r).quantize(Decimal("0.01"))
            except Exception:
                rate_val = Decimal("0.00")
            if rate_val < 0:
                rate_val = Decimal("0.00")

            try:
                dp = Decimal((row_discount_pcts[idx] if idx < len(row_discount_pcts) else "0") or "0").quantize(
                    Decimal("0.01")
                )
            except Exception:
                dp = Decimal("0.00")
            try:
                da = Decimal((row_discount_amts[idx] if idx < len(row_discount_amts) else "0") or "0").quantize(
                    Decimal("0.01")
                )
            except Exception:
                da = Decimal("0.00")
            if dp < 0:
                dp = Decimal("0.00")
            if da < 0:
                da = Decimal("0.00")

            base = qty_val * rate_val
            disc = Decimal("0.00")
            if dp > 0:
                disc = (base * dp) / Decimal("100")
            if da > 0:
                disc = da
            if disc > base:
                disc = base
            net = base - disc
            if net < 0:
                net = Decimal("0.00")

            tax_amount = (net * tax_percent) / Decimal("100") if tax_percent > 0 else Decimal("0.00")
            line_total = (net + tax_amount).quantize(Decimal("0.01"))
            total_amount += line_total
            any_item = True

            QuotationItem.objects.create(
                quotation=quotation,
                product_id=pid,
                qty=qty_val,
                rate=rate_val,
                tax=tax_percent,
                discount=disc.quantize(Decimal("0.01")),
                warehouse=warehouse,
                total=line_total,
            )

        if not any_item:
            messages.error(request, "Quotation must contain at least one item.")
            return redirect("commerce:quotation_edit", pk=quotation.id)

        quotation.date = q_date
        quotation.valid_till = valid_till
        quotation.remarks = remarks
        quotation.warehouse = warehouse
        quotation.total_amount = total_amount
        quotation.status = status
        quotation.save(update_fields=["date", "valid_till", "remarks", "warehouse", "total_amount", "status"])

        if (from_status or "") != (quotation.status or ""):
            action = "send" if quotation.status == Quotation.Status.SENT else "draft"
            note = "Status updated"
        else:
            action = "edit"
            note = "Edited"
        QuotationAuditLog.objects.create(
            quotation=quotation,
            action=action,
            from_status=from_status or "",
            to_status=quotation.status,
            performed_by=request.user,
            note=note,
        )

        messages.success(request, f"Quotation {quotation.quotation_number or '#' + str(quotation.id)} updated.")
        return redirect("commerce:quotation_detail", pk=quotation.id)


@login_required
@transaction.atomic
def quotation_action(request, pk: int, action: str):
    try:
        Quotation.objects.exists()
    except (OperationalError, ProgrammingError):
        messages.error(request, "Quotation module database tables are missing. Please run migrations.")
        return redirect("accounts:dashboard")
    quotation = (
        Quotation.objects.select_for_update()
        .select_related("party", "converted_order")
        .filter(id=pk, party__owner=request.user)
        .first()
    )
    if not quotation:
        messages.error(request, "Quotation not found.")
        return redirect("commerce:quotation_list")

    act = (action or "").strip().lower()
    cur = (quotation.status or "").strip().lower()

    if act == "verify":
        if cur != Quotation.Status.SENT:
            messages.error(request, "Only Sent quotations can be Verified.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        quotation.status = Quotation.Status.VERIFIED
        quotation.save(update_fields=["status"])
        QuotationAuditLog.objects.create(
            quotation=quotation,
            action="verify",
            from_status=cur,
            to_status=Quotation.Status.VERIFIED,
            performed_by=request.user,
            note="Verified",
        )
        messages.success(request, "Quotation verified.")
        return redirect("commerce:quotation_detail", pk=quotation.id)

    if act == "approve":
        if cur != Quotation.Status.VERIFIED:
            messages.error(request, "Only Verified quotations can be Approved.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        quotation.status = Quotation.Status.APPROVED
        quotation.save(update_fields=["status"])
        QuotationAuditLog.objects.create(
            quotation=quotation,
            action="approve",
            from_status=cur,
            to_status=Quotation.Status.APPROVED,
            performed_by=request.user,
            note="Approved",
        )
        messages.success(request, "Quotation approved.")
        return redirect("commerce:quotation_detail", pk=quotation.id)

    if act == "reject":
        if cur == Quotation.Status.CONVERTED:
            messages.error(request, "Converted quotation cannot be rejected.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        quotation.status = Quotation.Status.REJECTED
        quotation.save(update_fields=["status"])
        QuotationAuditLog.objects.create(
            quotation=quotation,
            action="reject",
            from_status=cur,
            to_status=Quotation.Status.REJECTED,
            performed_by=request.user,
            note="Rejected",
        )
        messages.success(request, "Quotation rejected.")
        return redirect("commerce:quotation_detail", pk=quotation.id)

    if act == "delete":
        if cur == Quotation.Status.CONVERTED:
            messages.error(request, "Converted quotation cannot be deleted.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        quotation.delete()
        messages.success(request, "Quotation deleted.")
        return redirect("commerce:quotation_list")

    if act == "convert":
        if cur != Quotation.Status.APPROVED:
            messages.error(request, "Only Approved quotations can be converted.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        if quotation.is_expired:
            messages.error(request, "Cannot convert an expired quotation.")
            return redirect("commerce:quotation_detail", pk=quotation.id)
        return redirect(f"{reverse('sales_order_create_root')}?quotation_id={quotation.id}")

    messages.error(request, "Invalid action.")
    return redirect("commerce:quotation_detail", pk=quotation.id)

# ---------------- Dashboard ----------------
@login_required
def user_commerce_dashboard(request):
    """Commerce dashboard inside user account area"""
    if not is_paid_user(request.user):
        messages.error(request, "🚫 You do not have access to Commerce features.")
        return redirect("/accounts/dashboard/")

    context = {
        "products": Product.objects.filter(owner=request.user),
        "orders": Order.objects.filter(owner=request.user),
        "warehouses": Warehouse.objects.filter(owner=request.user) if hasattr(Warehouse, "owner") else Warehouse.objects.all(),
        "invoices": Invoice.objects.filter(owner=request.user) if hasattr(Invoice, "owner") else Invoice.objects.all(),
        "stocks": Stock.objects.all(),
        "payments": Payment.objects.all(),
        "threads": ChatThread.objects.all(),
        "is_paid": True
    }
    return render(request, "commerce/user_commerce_dashboard.html", context)


# ---------------- Product ----------------
@login_required
def add_category(request):
    can_edit = erp_can_edit(request.user)
    can_delete = erp_can_delete(request.user)
    if request.method == "POST":
        if not can_edit:
            messages.error(request, "Permission denied: view-only role cannot add categories.")
            return redirect("commerce:add_category")
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not name:
            messages.error(request, "Please enter a category name.")
        elif Category.objects.filter(owner=request.user, name__iexact=name).exists():
            messages.error(request, "Category already exists.")
        else:
            Category.objects.create(
                name=name, description=description, owner=request.user
            )
            messages.success(request, "Category added successfully!")
            return redirect("commerce:add_category")

    categories = Category.objects.filter(owner=request.user).order_by("name")
    return render(request, "commerce/add_category.html", {"categories": categories, "can_edit": can_edit, "can_delete": can_delete})


@login_required
def category_edit(request, pk: int):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit categories.")
        return redirect("commerce:add_category")

    category = get_object_or_404(Category, id=pk, owner=request.user)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not name:
            messages.error(request, "Please enter a category name.")
        elif Category.objects.filter(owner=request.user, name__iexact=name).exclude(id=category.id).exists():
            messages.error(request, "Category already exists.")
        else:
            category.name = name
            category.description = description
            category.save(update_fields=["name", "description"])
            messages.success(request, "Category updated successfully!")
            return redirect("commerce:add_category")

    return render(request, "commerce/edit_category.html", {"category": category})


@login_required
def category_delete(request, pk: int):
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: you cannot delete categories.")
        return redirect("commerce:add_category")

    category = get_object_or_404(Category, id=pk, owner=request.user)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect("commerce:add_category")

    return render(request, "commerce/category_confirm_delete.html", {"category": category})


@login_required
def add_product(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add products.")
        return redirect("commerce:product_list")

    categories = Category.objects.filter(owner=request.user)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        min_stock = request.POST.get("min_stock")
        description = (request.POST.get("description") or "").strip()
        image = request.FILES.get("image")
        category_id = (request.POST.get("category") or "").strip()
        sku = (request.POST.get("sku") or "").strip()
        unit = (request.POST.get("unit") or "").strip() or "pcs"
        hsn_code = (request.POST.get("hsn_code") or "").strip()
        gst_rate = request.POST.get("gst_rate")

        if not sku:
            sku = generate_unique_sku()

        category = None
        if category_id:
            category = Category.objects.filter(id=category_id, owner=request.user).first()

        Product.objects.create(
            name=name,
            price=price,
            stock=stock,
            min_stock=min_stock or 0,
            image=image,
            description=description,
            category=category,
            sku=sku,
            unit=unit,
            hsn_code=hsn_code or None,
            gst_rate=gst_rate,
            owner=request.user,
        )
        messages.success(request, "Product added successfully!")
        return redirect("commerce:product_list")

    return render(request, "commerce/add_product.html", {"categories": categories})


@login_required
def product_list(request):
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    sku = (request.GET.get("sku") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()  # ok / low / out
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Product.objects.select_related("category").filter(owner=request.user)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category__name__icontains=category)
    if sku:
        qs = qs.filter(sku__icontains=sku)
    if status == "out":
        qs = qs.filter(stock__lte=0)
    elif status == "low":
        qs = qs.filter(stock__gt=0, stock__lte=F("min_stock"))
    elif status == "ok":
        qs = qs.filter(stock__gt=F("min_stock"))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "category": category,
        "sku": sku,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/product_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "commerce/product_list.html", context)

@login_required
def product_detail(request, id):
    product = get_object_or_404(Product, id=id, owner=request.user)
    return render(
        request,
        "commerce/product_detail.html",
        {"product": product}
    )


@login_required
def product_create(request):
    """
    Legacy alias for add_product.

    Keeps /commerce/products/new/ working with the unified add-product flow
    (including optional product image upload for portal catalog).
    """
    return add_product(request)

def product_edit(request, pk):
    """Edit existing product"""
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit products.")
        return redirect("commerce:product_list")

    product = get_object_or_404(Product, pk=pk, owner=request.user)

    if request.method == "POST":
        product.name = request.POST.get("name")
        product.price = request.POST.get("price")
        product.stock = request.POST.get("stock")
        product.description = request.POST.get("description")

        if not product.name or not product.price:
            messages.error(request, "Please fill all required fields.")
            return redirect("commerce:product_edit", pk=pk)

        product.save()
        messages.success(request, f"✅ Product '{product.name}' updated successfully!")
        return redirect("commerce:product_list")

    return render(request, "commerce/edit_product.html", {"product": product})

def product_delete(request, pk):
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can delete.")
        return redirect("commerce:product_list")

    product = get_object_or_404(Product, pk=pk, owner=request.user)

    if request.method == "POST":
        product.delete()
        messages.success(request, "✅ Product deleted successfully.")
        return redirect("commerce:product_list")  # adjust as per your list view name

    return render(request, "commerce/product_confirm_delete.html", {"product": product})

@login_required
def get_product_price(request, product_id):
    try:
        product = Product.objects.get(id=product_id, owner=request.user)
        return JsonResponse({"price": str(product.price)})
    except Product.DoesNotExist:
        return JsonResponse({"price": "0.00"})


@login_required
@require_GET
def get_product_stock(request, product_id):
    """
    Return per-warehouse stock for a product (used by PC Busy add-order popups).
    """
    product = get_object_or_404(Product, id=product_id, owner=request.user)

    all_warehouses = Warehouse.objects.all().order_by("name")
    stock_map = {
        s["warehouse_id"]: (s["quantity"] or 0)
        for s in Stock.objects.filter(product_id=product.id).values("warehouse_id", "quantity")
    }
    warehouses = [
        {"id": w.id, "name": w.name, "quantity": int(stock_map.get(w.id, 0))}
        for w in all_warehouses
    ]

    total = sum((w["quantity"] or 0) for w in warehouses) if warehouses else int(product.stock or 0)

    return JsonResponse(
        {
            "product": {
                "id": product.id,
                "name": product.name,
                "unit": product.unit,
                "stock": int(product.stock or 0),
            },
            "total": total,
            "warehouses": warehouses,
        }
    )

# ---------------- Warehouse ----------------
@login_required
def add_warehouse(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add warehouses.")
        return redirect("commerce:warehouse_list")

    if request.method == "POST":
        Warehouse.objects.create(
            name=request.POST.get("name"),
            location=request.POST.get("location"),
            capacity=request.POST.get("capacity", 0)
        )
        messages.success(request, "🏢 Warehouse added successfully!")
        return redirect("accounts:dashboard")
    return render(request, "commerce/add_warehouse.html")

@login_required
def warehouse_create(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add warehouses.")
        return redirect("commerce:warehouse_list")

    if request.method == "POST":
        form = WarehouseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("commerce:warehouse_list")
    else:
        form = WarehouseForm()
    return render(request, "commerce/warehouse_form.html", {"form": form, "title": "Add New Warehouse"})


@login_required
def warehouse_edit(request, pk):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit warehouses.")
        return redirect("commerce:warehouse_list")

    warehouse = get_object_or_404(Warehouse, pk=pk)
    if request.method == "POST":
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            form.save()
            return redirect("commerce:warehouse_list")
    else:
        form = WarehouseForm(instance=warehouse)
    return render(request, "commerce/warehouse_form.html", {"form": form, "title": "Edit Warehouse"})


@login_required
def warehouse_list(request):
    q = (request.GET.get("q") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Warehouse.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "warehouses": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/warehouse_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "commerce/warehouse_list.html", context)


@login_required
def warehouse_view(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    stocks = (
        Stock.objects.select_related("product")
        .filter(warehouse=warehouse)
        .filter(Q(product__owner=request.user) | Q(product__owner__isnull=True))
        .order_by("-updated_at", "product__name")
    )
    return render(request, "commerce/warehouse_view.html", {"warehouse": warehouse, "stocks": stocks})


@login_required
def warehouse_delete(request, pk):
    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can delete.")
        return redirect("commerce:warehouse_list")

    warehouse = get_object_or_404(Warehouse, pk=pk)
    if request.method == "POST":
        warehouse.delete()
        messages.success(request, "✅ Warehouse deleted successfully!")
        return redirect("commerce:warehouse_list")  # make sure this name exists in urls.py
    return render(request, "commerce/warehouse_confirm_delete.html", {"warehouse": warehouse})


# ---------------- Stock ----------------
@login_required
def add_stock(request):
    products = Product.objects.filter(owner=request.user)
    warehouses = Warehouse.objects.all()

    if request.method == "POST":
        product_id = request.POST.get("product")
        warehouse_id = request.POST.get("warehouse")
        qty = request.POST.get("quantity")

        # ✅ Validate inputs
        if not (product_id and warehouse_id and qty):
            messages.error(request, "Please select product, warehouse, and quantity.")
            return render(request, "commerce/add_stock.html", {"products": products, "warehouses": warehouses})

        product = Product.objects.filter(id=product_id, owner=request.user).first()
        if not product:
            messages.error(request, "Invalid product selected.")
            return redirect("commerce:add_stock")

        warehouse = Warehouse.objects.filter(id=warehouse_id).first()
        if not warehouse:
            messages.error(request, "Invalid warehouse selected.")
            return redirect("commerce:add_stock")


        try:
            qty = int(qty)
            if qty <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return redirect("commerce:add_stock")

        except ValueError:
            messages.error(request, "Invalid quantity value.")
            return redirect("commerce:add_stock")


        # ✅ Create Stock record
        Stock.objects.create(
            product=product,
            warehouse=warehouse,
            quantity=qty
        )

        messages.success(request, f"📦 {qty} units of {product.name} added to {warehouse.name} successfully!")
        return redirect("commerce:add_stock")


    # ✅ GET request → render form
    return render(request, "commerce/add_stock.html", {"products": products, "warehouses": warehouses})


# ---------------- Add Order ----------------
@login_required
def add_order(request):
    if request.method == "POST":
        try:
            with transaction.atomic():
                quotation_id_raw = (request.POST.get("quotation_id") or "").strip()
                locked_quotation = None
                if quotation_id_raw:
                    try:
                        quotation_id = int(quotation_id_raw)
                    except Exception:
                        quotation_id = None
                    if quotation_id:
                        locked_quotation = (
                            Quotation.objects.select_for_update()
                            .select_related("party", "warehouse", "converted_order")
                            .get(id=quotation_id, party__owner=request.user)
                        )
                        if (locked_quotation.status or "").lower() != Quotation.Status.APPROVED:
                            messages.error(request, "Only Approved quotations can be converted to an order.")
                            return redirect("commerce:quotation_detail", pk=locked_quotation.id)
                        if locked_quotation.is_expired:
                            messages.error(request, "Cannot convert an expired quotation.")
                            return redirect("commerce:quotation_detail", pk=locked_quotation.id)
                        if locked_quotation.converted_order_id:
                            messages.error(request, "Quotation is already converted.")
                            return redirect("commerce:quotation_detail", pk=locked_quotation.id)

                # Basic fields
                party_id = request.POST.get("party")
                order_type_raw = (request.POST.get("order_type") or "sale").strip()
                order_type = {"sale": "SALE", "purchase": "PURCHASE"}.get(order_type_raw.lower(), order_type_raw)
                reference = (request.POST.get("reference") or "").strip()
                notes = (request.POST.get("notes") or "").strip()
                if reference:
                    notes = f"Ref: {reference}\n{notes}".strip()

                warehouse_id = (request.POST.get("warehouse") or "").strip()
                order_date_raw = (request.POST.get("order_date") or "").strip()
                bill_sundry_lines = []
                raw_bill_sundry = request.POST.get("bill_sundry_json")
                if raw_bill_sundry:
                    try:
                        parsed = json.loads(raw_bill_sundry)
                        if isinstance(parsed, list):
                            for line in parsed:
                                if not isinstance(line, dict):
                                    continue
                                name = str(line.get("name") or "").strip()
                                narration = str(line.get("narration") or "").strip()
                                rate = str(line.get("rate") or "").strip()
                                try:
                                    amount = Decimal(str(line.get("amount") or "0")).quantize(Decimal("0.01"))
                                except Exception:
                                    amount = Decimal("0.00")
                                if name or narration or rate or amount != Decimal("0.00"):
                                    bill_sundry_lines.append(
                                        {
                                            "name": name,
                                            "narration": narration,
                                            "rate": rate,
                                            "amount": str(amount),
                                        }
                                    )
                    except Exception:
                        bill_sundry_lines = []

                if not party_id:
                    messages.error(request, "Please select a party.")
                    return redirect("commerce:add_order")

                party = Party.objects.filter(id=party_id, owner=request.user).first()
                if not party:
                    messages.error(request, "Invalid party selected.")
                    return redirect("commerce:add_order")

                if locked_quotation is not None:
                    if int(party.id) != int(locked_quotation.party_id):
                        messages.error(request, "Party cannot be changed for a quotation-linked order.")
                        return redirect(f"{reverse('sales_order_create_root')}?quotation_id={locked_quotation.id}")

                gst_enabled = str(request.POST.get("gst_enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
                gst_rate_raw = (request.POST.get("gst_rate") or "").strip()
                try:
                    gst_rate = Decimal(gst_rate_raw or "0").quantize(Decimal("0.01"))
                except Exception:
                    gst_rate = Decimal("0.00")
                tax_percent = gst_rate if gst_enabled else Decimal("0.00")

                warehouse = None
                if warehouse_id:
                    warehouse = Warehouse.objects.filter(id=warehouse_id).first()

                try:
                    order_date = timezone.now()
                    if order_date_raw:
                        order_date = timezone.make_aware(
                            datetime.strptime(order_date_raw, "%Y-%m-%d"),
                            timezone.get_current_timezone(),
                        )
                except Exception:
                    order_date = timezone.now()

                # Create Order
                order = Order.objects.create(
                    owner=request.user,
                    party=party,
                    warehouse=warehouse,
                    order_type=order_type,
                    status="pending",
                    notes=notes,
                    bill_sundry=bill_sundry_lines,
                    tax_percent=tax_percent,
                    order_source=("Quotation" if locked_quotation is not None else "Manual"),
                    quotation=locked_quotation,
                )

                # Lists
                products = request.POST.getlist("product[]")
                qtys = request.POST.getlist("qty[]")
                prices = request.POST.getlist("price[]")
                row_discount_pcts = request.POST.getlist("discount_percent[]")
                row_discount_amts = request.POST.getlist("discount_amount[]")

                # Validate at least one valid row
                valid_items = False

                for idx, (p, q, r) in enumerate(zip(products, qtys, prices)):
                    p = (p or "").strip()
                    q = (q or "").strip()
                    r = (r or "").strip()
                    if not (p and q and r):
                        continue
                    if not Product.objects.filter(id=p, owner=request.user).exists():
                        continue
                    try:
                        qty_val = int(float(q))
                    except Exception:
                        continue
                    if qty_val <= 0:
                        continue
                    try:
                        price_val = Decimal(str(r)).quantize(Decimal("0.01"))
                    except Exception:
                        continue

                    try:
                        dp = Decimal(str(row_discount_pcts[idx] if idx < len(row_discount_pcts) else "0"))
                    except Exception:
                        dp = Decimal("0")
                    try:
                        da = Decimal(str(row_discount_amts[idx] if idx < len(row_discount_amts) else "0"))
                    except Exception:
                        da = Decimal("0")

                    if dp < 0:
                        dp = Decimal("0")
                    if dp > 100:
                        dp = Decimal("100")
                    if da < 0:
                        da = Decimal("0")

                    base = Decimal(qty_val) * price_val
                    discount = Decimal("0.00")
                    if dp > 0:
                        discount = (base * dp) / Decimal("100")
                    if da > 0:
                        discount = da
                    net = base - discount
                    if net < 0:
                        net = Decimal("0.00")
                    effective_unit_price = (net / Decimal(qty_val)).quantize(Decimal("0.01")) if qty_val else price_val

                    valid_items = True
                    OrderItem.objects.create(
                        order=order,
                        product_id=p,
                        qty=qty_val,
                        price=effective_unit_price,
                        tax_percent=tax_percent,
                        warehouse=warehouse,
                    )

                if not valid_items:
                    messages.error(request, "Order must contain at least one item.")
                    order.delete()
                    return redirect("commerce:add_order")

                # Recompute totals after items are created
                order.save()

                # Smart BI: Festival Sale Mode (auto-discount)
                try:
                    from smart_bi.services.festival import apply_festival_discount

                    apply_festival_discount(order, day=order_date.date(), save=True)
                except Exception:
                    pass

                # Align document date (best-effort, keeps list sorting consistent).
                Order.objects.filter(id=order.id).update(created_at=order_date)

                messages.success(request, f"Order #{order.id} created successfully")

                # Auto-send notifications
                party = order.party
                if party.email:
                    # Send email
                    pass  # Implement email sending
                if party.whatsapp_number:
                    # Send WhatsApp
                    pass  # Implement WhatsApp sending
                if party.mobile:
                    # Send SMS
                    pass  # Implement SMS sending

                # Redirect to order list
                if locked_quotation is not None:
                    from_status = locked_quotation.status
                    locked_quotation.status = Quotation.Status.CONVERTED
                    locked_quotation.converted_order = order
                    locked_quotation.save(update_fields=["status", "converted_order"])
                    QuotationAuditLog.objects.create(
                        quotation=locked_quotation,
                        action="convert",
                        from_status=from_status,
                        to_status=Quotation.Status.CONVERTED,
                        performed_by=request.user,
                        note=f"Order #{order.id} created",
                    )
                    return redirect("commerce:order_detail", pk=order.id)

                return redirect("commerce:order_list")

        except Exception as e:
            messages.error(request, f"Error while saving order: {e}")
            return redirect("commerce:add_order")

    # GET REQUEST
    parties = Party.objects.filter(owner=request.user).order_by("name")
    products = Product.objects.filter(owner=request.user).order_by("name")
    warehouses = Warehouse.objects.all().order_by("name")

    quotation_id_raw = (request.GET.get("quotation_id") or "").strip()
    quotation = None
    initial_party_id = ""
    initial_items = []
    initial_warehouse_id = ""
    initial_order_date = ""
    initial_order_type = (request.GET.get("order_type") or "").strip().lower() or "sale"
    if initial_order_type not in {"sale", "purchase"}:
        initial_order_type = "sale"
    initial_gst_rate = ""
    initial_gst_enabled = True
    initial_notes = ""

    if quotation_id_raw:
        try:
            quotation_id = int(quotation_id_raw)
        except Exception:
            quotation_id = None
        if quotation_id:
            quotation = (
                Quotation.objects.select_related("party", "warehouse", "converted_order")
                .prefetch_related("items__product")
                .filter(id=quotation_id, party__owner=request.user)
                .first()
            )
            if quotation:
                if (quotation.status or "").lower() != Quotation.Status.APPROVED:
                    messages.error(request, "Only Approved quotations can be converted to an order.")
                    return redirect("commerce:quotation_detail", pk=quotation.id)
                if quotation.is_expired:
                    messages.error(request, "Cannot convert an expired quotation.")
                    return redirect("commerce:quotation_detail", pk=quotation.id)
                if quotation.converted_order_id:
                    messages.error(request, "Quotation is already converted.")
                    return redirect("commerce:quotation_detail", pk=quotation.id)

                initial_party_id = str(quotation.party_id)
                initial_warehouse_id = str(quotation.warehouse_id or "")
                initial_order_date = quotation.date.strftime("%Y-%m-%d") if quotation.date else ""

                # GST: best-effort from first line (module currently stores same % per line).
                first_line = quotation.items.all().first()
                if first_line and first_line.tax is not None:
                    try:
                        initial_gst_rate = str(Decimal(str(first_line.tax)).quantize(Decimal("0.01")))
                    except Exception:
                        initial_gst_rate = ""
                initial_gst_enabled = bool(initial_gst_rate and Decimal(initial_gst_rate or "0") > 0)

                initial_items = [
                    {
                        "product_id": it.product_id,
                        "product_name": it.product.name,
                        "qty": it.qty,
                        "rate": it.rate,
                        "discount": it.discount,
                    }
                    for it in quotation.items.all()
                ]
                initial_notes = quotation.remarks or ""

    # Prefill support (one-click PO) when not converting from quotation.
    if quotation is None:
        party_id_prefill = (request.GET.get("party_id") or request.GET.get("party") or "").strip()
        if party_id_prefill:
            try:
                pid = int(party_id_prefill)
            except Exception:
                pid = None
            if pid:
                pre_party = Party.objects.filter(id=pid, owner=request.user).only("id").first()
                if pre_party:
                    initial_party_id = str(pre_party.id)

        product_id_prefill = (request.GET.get("product_id") or request.GET.get("product") or "").strip()
        if product_id_prefill:
            try:
                prod_id = int(product_id_prefill)
            except Exception:
                prod_id = None
            if prod_id:
                pre_product = Product.objects.filter(id=prod_id, owner=request.user).only("id", "name", "price").first()
                if pre_product:
                    qty_raw = (request.GET.get("qty") or "1").strip()
                    price_raw = (request.GET.get("price") or "").strip()
                    try:
                        qty_val = int(float(qty_raw))
                    except Exception:
                        qty_val = 1
                    if qty_val <= 0:
                        qty_val = 1
                    try:
                        rate_val = Decimal(price_raw).quantize(Decimal("0.01")) if price_raw else pre_product.price
                    except Exception:
                        rate_val = pre_product.price

                    initial_items = [
                        {
                            "product_id": pre_product.id,
                            "product_name": pre_product.name,
                            "qty": qty_val,
                            "rate": rate_val,
                            "discount": Decimal("0.00"),
                        }
                    ]
    return render(
        request,
        "commerce/add_order_smooth.html",
        {
            "parties": parties,
            "products": products,
            "warehouses": warehouses,
            "quotation": quotation,
            "quotation_id": (quotation.id if quotation else ""),
            "initial_party_id": initial_party_id,
            "initial_items": initial_items,
            "initial_warehouse_id": initial_warehouse_id,
            "initial_order_date": initial_order_date,
            "initial_order_type": initial_order_type,
            "initial_gst_rate": initial_gst_rate,
            "initial_gst_enabled": initial_gst_enabled,
            "initial_notes": initial_notes,
        },
    )


def _order_list_view(request, *, base_filter: dict, page_title: str, template_name: str):
    q = (request.GET.get("q") or "").strip()
    order_type = (request.GET.get("type") or "").strip().upper()
    status = (request.GET.get("status") or "").strip().lower()
    source = (request.GET.get("source") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = (
        Order.objects.filter(owner=request.user, **(base_filter or {}))
        .select_related("party", "agent", "assigned_to", "warehouse")
        .prefetch_related("invoice")
    )

    if q:
        qs = qs.filter(Q(party__name__icontains=q) | Q(notes__icontains=q) | Q(order_source__icontains=q))
    if source:
        qs = qs.filter(order_source__icontains=source)
    if order_type in {"SALE", "PURCHASE"} and not base_filter.get("order_type__iexact"):
        qs = qs.filter(order_type=order_type)
    if status:
        qs = qs.filter(status__iexact=status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    items_subtotal = Sum(
        ExpressionWrapper(F("items__qty") * F("items__price"), output_field=DecimalField(max_digits=14, decimal_places=2))
    )
    qs = qs.annotate(items_subtotal=items_subtotal, items_count=Count("items")).order_by("-created_at", "-id")

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    # Compute final totals without extra DB calls.
    for o in page_obj.object_list:
        try:
            subtotal = o.items_subtotal or Decimal("0.00")
        except Exception:
            subtotal = Decimal("0.00")
        try:
            total = subtotal - (o.discount_amount or Decimal("0.00")) + (o.tax_amount or Decimal("0.00")) + o.bill_sundry_total()
        except Exception:
            total = subtotal
        o.list_total = total

    context = {
        "orders": page_obj.object_list,
        "page_obj": page_obj,
        "page_title": page_title,
        "q": q,
        "type": order_type,
        "status": status,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
        "base_order_type": (base_filter.get("order_type__iexact") or "").upper(),
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/order_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, template_name, context)


@login_required
def sales_order_list(request):
    return _order_list_view(
        request,
        base_filter={"order_type__iexact": "sale"},
        page_title="Sales Orders",
        template_name="commerce/sales_order_list.html",
    )


@login_required
def purchase_order_list(request):
    return _order_list_view(
        request,
        base_filter={"order_type__iexact": "purchase"},
        page_title="Purchase Orders",
        template_name="commerce/purchase_order_list.html",
    )


# ---------------- Order List (User Side) ----------------
@login_required
def order_list(request):
    return _order_list_view(request, base_filter={}, page_title="Order List", template_name="commerce/order_list.html")

# ---------------- Order View (User Side) ----------------
@login_required
def view_order(request, order_id):
    order = get_object_or_404(Order.objects.select_related("party", "warehouse"), id=order_id, owner=request.user)
    items = list(order.items.select_related("product", "warehouse").all())
    try:
        total_qty = sum([Decimal(str(it.qty or 0)) for it in items], Decimal("0.00"))
        invoiced_qty = sum([Decimal(str(it.invoiced_qty or 0)) for it in items], Decimal("0.00"))
    except Exception:
        total_qty = Decimal("0.00")
        invoiced_qty = Decimal("0.00")
    order.total_qty = total_qty
    order.invoiced_qty = invoiced_qty
    if invoiced_qty <= Decimal("0.00"):
        order.conversion_status = Order.ConversionStatus.PENDING
    elif invoiced_qty < total_qty:
        order.conversion_status = Order.ConversionStatus.PARTIAL
    else:
        order.conversion_status = Order.ConversionStatus.COMPLETED
    vouchers = (
        SalesVoucher.objects.filter(order=order)
        .select_related("party", "order")
        .prefetch_related("items__product", "items__warehouse")
        .order_by("-invoice_no")
    )
    return render(request, "commerce/order_detail.html", {"order": order, "items": items, "vouchers": vouchers})

# ---------------- Order Details (User Side) ----------------
@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("party", "warehouse"), pk=pk, owner=request.user)
    items = list(order.items.select_related("product", "warehouse").all())
    try:
        total_qty = sum([Decimal(str(it.qty or 0)) for it in items], Decimal("0.00"))
        invoiced_qty = sum([Decimal(str(it.invoiced_qty or 0)) for it in items], Decimal("0.00"))
    except Exception:
        total_qty = Decimal("0.00")
        invoiced_qty = Decimal("0.00")
    order.total_qty = total_qty
    order.invoiced_qty = invoiced_qty
    if invoiced_qty <= Decimal("0.00"):
        order.conversion_status = Order.ConversionStatus.PENDING
    elif invoiced_qty < total_qty:
        order.conversion_status = Order.ConversionStatus.PARTIAL
    else:
        order.conversion_status = Order.ConversionStatus.COMPLETED
    vouchers = (
        SalesVoucher.objects.filter(order=order)
        .select_related("party", "order")
        .prefetch_related("items__product", "items__warehouse")
        .order_by("-invoice_no")
    )
    return render(request, "commerce/order_detail.html", {"order": order, "items": items, "vouchers": vouchers})


@login_required
def sales_order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.filter(_order_access_q(request.user)),
        id=order_id,
        order_type__iexact="sale",
    )
    items = order.items.select_related("product")
    return render(
        request,
        "commerce/sales_order_detail.html",
        {
            "order": order,
            "items": items,
        },
    )


# ---------------- Order Action (User Side) ----------------
@login_required
def order_action(request, order_id, action):
    order = get_object_or_404(Order, id=order_id, owner=request.user)

    valid_actions = ["accept", "reject", "cancel"]
    if action not in valid_actions:
        messages.error(request, "Invalid action.")
        return redirect("commerce:order_list")

    # Accept Logic
    if action == "accept":
        order.status = "accepted"
        order.save()
        messages.success(request, f"Order #{order.id} accepted")

        # If this order originated from Storefront, keep StoreOrder in sync.
        try:
            from storefront.models import StoreOrder, StoreOrderStatusEvent

            so = StoreOrder.objects.filter(commerce_order_id=order.id).first()
            if so and so.status != StoreOrder.Status.ACCEPTED:
                so.status = StoreOrder.Status.ACCEPTED
                so.save(update_fields=["status", "updated_at"])
                StoreOrderStatusEvent.objects.create(order=so, status=so.status, note="Accepted in Billing (central)")
        except Exception:
            pass

        # Accept ke baad automatic Voucher Page
        return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={order.id}")

    # Reject Logic
    if action == "reject":
        order.status = "rejected"
        order.save()
        messages.error(request, f"Order #{order.id} rejected")
        try:
            from storefront.models import StoreOrder, StoreOrderStatusEvent

            so = StoreOrder.objects.filter(commerce_order_id=order.id).first()
            if so and so.status != StoreOrder.Status.REJECTED:
                so.status = StoreOrder.Status.REJECTED
                so.save(update_fields=["status", "updated_at"])
                StoreOrderStatusEvent.objects.create(order=so, status=so.status, note="Rejected in Billing (central)")
        except Exception:
            pass

    # Cancel Logic
    if action == "cancel":
        order.status = "cancelled"
        order.save()
        messages.warning(request, f"Order #{order.id} cancelled")
        try:
            from storefront.models import StoreOrder, StoreOrderStatusEvent

            so = StoreOrder.objects.filter(commerce_order_id=order.id).first()
            if so and so.status in {StoreOrder.Status.PENDING, StoreOrder.Status.ACCEPTED}:
                so.status = StoreOrder.Status.CANCELLED
                so.save(update_fields=["status", "updated_at"])
                StoreOrderStatusEvent.objects.create(order=so, status=so.status, note="Cancelled in Billing (central)")
        except Exception:
            pass

    return redirect("commerce:order_list")

# ---------------- Sales Voucher ----------------
class SalesVoucherCreateView(LoginRequiredMixin, View):
    template_name = "commerce/sales_voucher_create.html"

    def _get_order_id(self, request, **kwargs):
        raw = (request.POST.get("order_id") or request.GET.get("order_id") or "").strip()
        if not raw and "order_id" in kwargs:
            raw = str(kwargs.get("order_id") or "").strip()
        try:
            return int(raw) if raw else None
        except Exception:
            return None

    def _get_order(self, request, order_id: int | None):
        if not order_id:
            return None
        return get_object_or_404(
            Order.objects.select_related("party", "warehouse").prefetch_related("items__product"),
            id=order_id,
            owner=request.user,
        )

    def _attach_item_map(self, order):
        # Allow forms/formsets to compute remaining qty without extra DB queries.
        items = list(order.items.all())
        order._items_by_id = {int(it.id): it for it in items if it.id is not None}
        return items

    def _get_formset_cls(self, *, extra: int):
        return modelformset_factory(
            SalesVoucherItem,
            form=SalesVoucherItemForm,
            formset=BaseSalesVoucherItemFormSet,
            extra=extra,
            can_delete=True,
        )

    def _initial_items_from_order(self, order_items):
        initial = []
        for it in order_items:
            remaining = None
            try:
                remaining = Decimal(str(it.qty or 0)) - (it.invoiced_qty or Decimal("0.00"))
            except Exception:
                remaining = None
            if remaining is None or remaining <= Decimal("0.00"):
                continue

            gst_rate = None
            try:
                if it.tax_percent is not None:
                    gst_rate = Decimal(str(it.tax_percent))
            except Exception:
                gst_rate = None
            if gst_rate is None:
                try:
                    gst_rate = Decimal(str(it.order.tax_percent or 0))
                except Exception:
                    gst_rate = Decimal("0.00")

            try:
                gst_rate_int = int(Decimal(str(gst_rate)).quantize(Decimal("1")))
            except Exception:
                gst_rate_int = 0
            if gst_rate_int not in {0, 5, 12, 18, 28}:
                gst_rate_int = 0

            initial.append(
                {
                    "product": it.product_id,
                    "qty": remaining,
                    "rate": it.price,
                    "gst_rate": gst_rate_int,
                    "warehouse": (it.warehouse_id or getattr(it.order, "warehouse_id", None)),
                    "source_order_item": it.id,
                }
            )
        return initial

    def get(self, request, *args, **kwargs):
        order_id = self._get_order_id(request, **kwargs)
        order = self._get_order(request, order_id)
        order_items = []
        initial_items = []
        if order is not None:
            order_items = self._attach_item_map(order)

            all_remaining = [
                (Decimal(str(it.qty or 0)) - (it.invoiced_qty or Decimal("0.00"))) for it in order_items
            ]
            if not any(r > 0 for r in all_remaining):
                messages.error(request, "This order is already fully converted to vouchers.")
                return redirect("commerce:order_detail", pk=order.id)

            # NOTE: formset `initial` is only applied to extra forms. If `extra=0`, nothing renders.
            initial_items = self._initial_items_from_order(order_items)

        voucher_form = SalesVoucherForm(
            user=request.user,
            order=order,
            initial={
                "party": getattr(order, "party_id", None) if order else None,
                "is_gst": True,
                "date": timezone.localdate(),
            },
        )

        extra = (len(initial_items) if order else 1)
        FormSetCls = self._get_formset_cls(extra=extra)
        formset = FormSetCls(
            queryset=SalesVoucherItem.objects.none(),
            prefix="items",
            form_kwargs={"user": request.user, "order": order},
            order=order,
            initial=(initial_items if order else None),
        )

        return render(
            request,
            self.template_name,
            {
                "order": order,
                "voucher_form": voucher_form,
                "formset": formset,
            },
        )

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order_id = self._get_order_id(request, **kwargs)
        order = self._get_order(request, order_id)

        order_items = []
        if order is not None:
            order_items = self._attach_item_map(order)

        voucher_form = SalesVoucherForm(request.POST, user=request.user, order=order)

        extra = 0 if order else 1
        FormSetCls = self._get_formset_cls(extra=extra)
        formset = FormSetCls(
            request.POST,
            queryset=SalesVoucherItem.objects.none(),
            prefix="items",
            form_kwargs={"user": request.user, "order": order},
            order=order,
        )

        if not (voucher_form.is_valid() and formset.is_valid()):
            return render(
                request,
                self.template_name,
                {
                    "order": order,
                    "voucher_form": voucher_form,
                    "formset": formset,
                },
            )

        # Lock order + items for safe partial conversion.
        locked_order = None
        locked_items_by_id = {}
        if order is not None:
            locked_order = (
                Order.objects.select_for_update()
                .select_related("party", "warehouse")
                .get(id=order.id, owner=request.user)
            )
            locked_items = list(
                OrderItem.objects.select_for_update()
                .select_related("product", "warehouse")
                .filter(order=locked_order)
            )
            locked_items_by_id = {int(it.id): it for it in locked_items if it.id is not None}

            all_remaining = [
                (Decimal(str(it.qty or 0)) - (it.invoiced_qty or Decimal("0.00"))) for it in locked_items
            ]
            if not any(r > 0 for r in all_remaining):
                messages.error(request, "This order is already fully converted to vouchers.")
                return redirect("commerce:order_detail", pk=locked_order.id)
            try:
                if int(voucher_form.cleaned_data["party"].id) != int(locked_order.party_id):
                    messages.error(request, "Party cannot be changed for an order-linked voucher.")
                    return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={locked_order.id}")
            except Exception:
                pass

        # Build deductions (race-safe) and ensure at least one line.
        per_order_item_deduct = {}
        has_any_line = False
        for form in formset.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            product = form.cleaned_data.get("product")
            qty = form.cleaned_data.get("qty")
            src = form.cleaned_data.get("source_order_item")
            if not product or qty is None:
                continue
            qty_dec = Decimal(str(qty))
            if qty_dec <= 0:
                continue
            has_any_line = True

            if locked_order is not None:
                if not src:
                    messages.error(request, "Invalid order item reference.")
                    return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={locked_order.id}")
                locked_src = locked_items_by_id.get(int(src.id))
                if not locked_src:
                    messages.error(request, "Invalid order item reference.")
                    return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={locked_order.id}")
                per_order_item_deduct[locked_src.id] = per_order_item_deduct.get(locked_src.id, Decimal("0.00")) + qty_dec

        if not has_any_line:
            messages.error(request, "Please add at least one voucher item.")
            if locked_order is not None:
                return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={locked_order.id}")
            return redirect(reverse("commerce:sales_voucher_create"))

        if locked_order is not None:
            for src_id, qty_sum in per_order_item_deduct.items():
                it = locked_items_by_id[int(src_id)]
                remaining = Decimal(str(it.qty or 0)) - (it.invoiced_qty or Decimal("0.00"))
                if qty_sum > remaining:
                    messages.error(request, f"Cannot invoice more than remaining qty for {it.product or 'item'}.")
                    return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={locked_order.id}")

        voucher = voucher_form.save(commit=False)
        voucher.order = locked_order if locked_order is not None else None
        voucher.total_amount = Decimal("0.00")
        voucher.save()

        total_amount = Decimal("0.00")

        for form in formset.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            product = form.cleaned_data.get("product")
            qty = form.cleaned_data.get("qty")
            rate = form.cleaned_data.get("rate") or Decimal("0.00")
            gst_rate = form.cleaned_data.get("gst_rate") or Decimal("0.00")
            warehouse = form.cleaned_data.get("warehouse")
            src = form.cleaned_data.get("source_order_item")

            if not product or qty is None:
                continue
            qty_dec = Decimal(str(qty))
            if qty_dec <= 0:
                continue

            line_amount = qty_dec * Decimal(str(rate))
            gst_amount = (line_amount * Decimal(str(gst_rate))) / Decimal("100") if voucher.is_gst else Decimal("0.00")
            total_amount += line_amount + gst_amount

            SalesVoucherItem.objects.create(
                voucher=voucher,
                product=product,
                qty=qty_dec,
                rate=Decimal(str(rate)),
                gst_rate=Decimal(str(gst_rate)),
                warehouse=warehouse,
                source_order_item=(locked_items_by_id.get(int(src.id)) if (locked_order is not None and src) else None),
            )

        if locked_order is not None:
            for src_id, qty_sum in per_order_item_deduct.items():
                it = locked_items_by_id[int(src_id)]
                it.invoiced_qty = (it.invoiced_qty or Decimal("0.00")) + qty_sum
                it.save(update_fields=["invoiced_qty"])
            locked_order.refresh_conversion_totals(save=True)
            if (locked_order.status or "").lower() not in {"cancelled", "rejected"}:
                if locked_order.conversion_status == Order.ConversionStatus.PARTIAL:
                    locked_order.status = "partial"
                elif locked_order.conversion_status == Order.ConversionStatus.COMPLETED:
                    locked_order.status = "completed"
                else:
                    locked_order.status = "pending"
                locked_order.save(update_fields=["status"])

        SalesVoucher.objects.filter(invoice_no=voucher.invoice_no).update(total_amount=total_amount)

        messages.success(request, f"Sales Voucher #{voucher.invoice_no} created successfully.")
        if locked_order is not None:
            return redirect("commerce:order_detail", pk=locked_order.id)
        return redirect("commerce:sales_voucher_detail", invoice_no=voucher.invoice_no)


@login_required
@transaction.atomic
def sales_voucher_quick_create(request):
    """
    Busy/Tally-style voucher entry (grid) that creates:
    - Order (SALE/PURCHASE)
    - Invoice (posts to GL + Stock via ledger signals)
    - Optional Payment (posts to GL via ledger signals)
    """

    initial_party_id = (request.GET.get("party") or "").strip()
    parties = Party.objects.filter(owner=request.user).order_by("name")
    products = Product.objects.filter(owner=request.user).order_by("name")
    warehouses = Warehouse.objects.all().order_by("name")

    if request.method == "POST":
        pending_order_id = (request.POST.get("pending_order_id") or "").strip()
        dup_action = (request.POST.get("dup_action") or "").strip().lower()
        force_duplicate = (request.POST.get("force_duplicate") or "").strip() == "1"

        pending_order_pk = None
        if pending_order_id:
            try:
                pending_order_pk = int(pending_order_id)
            except Exception:
                pending_order_pk = None

        if pending_order_pk and dup_action == "cancel":
            pending = Order.objects.filter(id=pending_order_pk, owner=request.user).first()
            if pending and not hasattr(pending, "invoice"):
                pending.delete()
            messages.info(request, "Voucher cancelled.")
            return redirect("commerce:sales_voucher_quick_create")

        submit_action = (request.POST.get("submit_action") or "").strip().lower()
        party_id = (request.POST.get("party") or "").strip()
        voucher_type_raw = (request.POST.get("voucher_type") or "SALE").strip().upper()
        voucher_type = "PURCHASE" if voucher_type_raw == "PURCHASE" else "SALE"

        warehouse_id = (request.POST.get("warehouse") or "").strip()
        voucher_date_raw = (request.POST.get("voucher_date") or "").strip()

        gst_enabled = str(request.POST.get("gst_enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
        gst_rate_raw = (request.POST.get("gst_rate") or "").strip()

        payment_mode = (request.POST.get("payment_mode") or "").strip()
        paid_amount_raw = (request.POST.get("paid_amount") or "").strip()
        payment_reference = (request.POST.get("payment_reference") or "").strip()

        notes = (request.POST.get("notes") or "").strip()

        order = None
        if pending_order_pk:
            order = get_object_or_404(
                Order.objects.select_related("party", "warehouse").prefetch_related("items__product"),
                id=pending_order_pk,
                owner=request.user,
            )
            party = order.party
            warehouse = order.warehouse
        else:
            if not party_id:
                messages.error(request, "Please select a party.")
                return redirect("commerce:sales_voucher_quick_create")

            party = Party.objects.filter(id=party_id, owner=request.user).first()
            if not party:
                messages.error(request, "Invalid party selected.")
                return redirect("commerce:sales_voucher_quick_create")

            warehouse = None
            if warehouse_id:
                warehouse = Warehouse.objects.filter(id=warehouse_id).first()

        try:
            voucher_date = timezone.now()
            if voucher_date_raw:
                # Store as local midnight (best-effort). We update created_at via queryset update.
                voucher_date = timezone.make_aware(
                    datetime.strptime(voucher_date_raw, "%Y-%m-%d"),
                    timezone.get_current_timezone(),
                )
        except Exception:
            voucher_date = timezone.now()

        try:
            gst_rate = Decimal(gst_rate_raw or "0").quantize(Decimal("0.01"))
        except Exception:
            gst_rate = Decimal("0.00")

        tax_percent = gst_rate if gst_enabled else Decimal("0.00")

        try:
            paid_amount = Decimal(paid_amount_raw or "0").quantize(Decimal("0.01"))
        except Exception:
            paid_amount = Decimal("0.00")
        if paid_amount < 0:
            paid_amount = Decimal("0.00")

        bill_sundry_lines = []
        raw_bill_sundry = request.POST.get("bill_sundry_json")
        if raw_bill_sundry:
            try:
                parsed = json.loads(raw_bill_sundry)
                if isinstance(parsed, list):
                    for line in parsed:
                        if not isinstance(line, dict):
                            continue
                        name = str(line.get("name") or "").strip()
                        narration = str(line.get("narration") or "").strip()
                        rate = str(line.get("rate") or "").strip()
                        try:
                            amount = Decimal(str(line.get("amount") or "0")).quantize(Decimal("0.01"))
                        except Exception:
                            amount = Decimal("0.00")
                        if name or narration or rate or amount != Decimal("0.00"):
                            bill_sundry_lines.append(
                                {
                                    "name": name,
                                    "narration": narration,
                                    "rate": rate,
                                    "amount": str(amount),
                                }
                            )
            except Exception:
                bill_sundry_lines = []

        if order is None:
            order = Order.objects.create(
                owner=request.user,
                party=party,
                warehouse=warehouse,
                order_type=voucher_type,
                status="accepted",
                notes=notes,
                order_source="Voucher",
                tax_percent=tax_percent,
                bill_sundry=bill_sundry_lines,
            )

            product_ids = request.POST.getlist("product[]")
            qtys = request.POST.getlist("qty[]")
            prices = request.POST.getlist("price[]")
            row_discount_pcts = request.POST.getlist("discount_percent[]")
            row_discount_amts = request.POST.getlist("discount_amount[]")

            valid_items = False
            for idx, (pid, qty_raw, price_raw) in enumerate(zip(product_ids, qtys, prices)):
                pid = (pid or "").strip()
                if not pid:
                    continue
                if not Product.objects.filter(id=pid, owner=request.user).exists():
                    continue

                try:
                    qty_val = int(float(qty_raw))
                except Exception:
                    continue
                if qty_val <= 0:
                    continue

                try:
                    price_val = Decimal(str(price_raw)).quantize(Decimal("0.01"))
                except Exception:
                    continue
                if price_val < 0:
                    price_val = Decimal("0.00")

                try:
                    dp = Decimal(str(row_discount_pcts[idx] if idx < len(row_discount_pcts) else "0"))
                except Exception:
                    dp = Decimal("0")
                try:
                    da = Decimal(str(row_discount_amts[idx] if idx < len(row_discount_amts) else "0"))
                except Exception:
                    da = Decimal("0")

                if dp < 0:
                    dp = Decimal("0")
                if dp > 100:
                    dp = Decimal("100")
                if da < 0:
                    da = Decimal("0")

                base = Decimal(qty_val) * price_val
                discount = Decimal("0.00")
                if dp > 0:
                    discount = (base * dp) / Decimal("100")
                if da > 0:
                    discount = da
                net = base - discount
                if net < 0:
                    net = Decimal("0.00")

                effective_unit_price = (net / Decimal(qty_val)).quantize(Decimal("0.01")) if qty_val else price_val

                OrderItem.objects.create(
                    order=order,
                    product_id=pid,
                    qty=qty_val,
                    price=effective_unit_price,
                )
                valid_items = True

            if not valid_items:
                order.delete()
                messages.error(request, "Voucher must contain at least one item.")
                return redirect("commerce:sales_voucher_quick_create")

        # Compute totals now that items exist (or refresh totals on resume).
        if not order.items.exists():
            order.delete()
            messages.error(request, "Voucher must contain at least one item.")
            return redirect("commerce:sales_voucher_quick_create")
        order.save()

        # Smart BI: Festival Sale Mode (auto-discount)
        try:
            from smart_bi.services.festival import apply_festival_discount

            apply_festival_discount(order, day=voucher_date.date(), save=True)
        except Exception:
            pass

        if hasattr(order, "invoice"):
            messages.warning(request, "Invoice already exists for this voucher.")
            return redirect("commerce:invoice_view", invoice_id=order.invoice.id)

        # Smart BI: Duplicate invoice detection (pre-create warning)
        try:
            from smart_bi.models import DuplicateInvoiceSettings
            from smart_bi.services.duplicate_invoices import find_possible_duplicate_invoices

            dup_settings = DuplicateInvoiceSettings.get_for_owner(request.user)
            candidates = find_possible_duplicate_invoices(order=order, settings=dup_settings, max_results=5)
        except Exception:
            candidates = []

        if candidates and not force_duplicate:
            continue_payload = {
                "pending_order_id": str(order.id),
                "force_duplicate": "1",
                "submit_action": submit_action,
                "voucher_type": voucher_type,
                "warehouse": warehouse_id,
                "voucher_date": voucher_date_raw,
                "gst_enabled": "1" if gst_enabled else "0",
                "gst_rate": str(gst_rate),
                "payment_mode": payment_mode,
                "paid_amount": str(paid_amount),
                "payment_reference": payment_reference,
                "notes": notes,
                "party": str(getattr(party, "id", "") or ""),
            }
            cancel_payload = {"pending_order_id": str(order.id), "dup_action": "cancel"}
            return render(
                request,
                "smart_bi/duplicate_invoice_warning.html",
                {
                    "source": "commerce.sales_voucher_quick_create",
                    "action_url": "",
                    "order": order,
                    "new_amount": order.total_amount(),
                    "candidates": candidates,
                    "continue_payload": continue_payload,
                    "cancel_payload": cancel_payload,
                    "cancel_url": reverse("commerce:sales_voucher_quick_create"),
                },
            )

        invoice = Invoice.objects.create(
            order=order,
            gst_type="GST" if gst_enabled else "NON_GST",
        )

        # Smart BI: log duplicate candidates (post-create)
        try:
            from smart_bi.services.duplicate_invoices import log_possible_duplicates

            if candidates:
                log_possible_duplicates(
                    owner=request.user,
                    created_by=request.user,
                    invoice=invoice,
                    candidates=candidates,
                )
        except Exception:
            pass

        # Align document dates (used by GL/stock posting via on_commit).
        Order.objects.filter(id=order.id).update(created_at=voucher_date)
        Invoice.objects.filter(id=invoice.id).update(created_at=voucher_date)

        # Refresh invoice amount (auto-set in model save). Keep it in sync with order totals.
        invoice.refresh_from_db(fields=["amount"])

        if paid_amount > 0:
            # Clamp paid amount to invoice amount to avoid negative balances in UI.
            if invoice.amount and paid_amount > invoice.amount:
                paid_amount = invoice.amount

            payment = Payment.objects.create(
                invoice=invoice,
                amount=paid_amount,
                method=payment_mode or None,
                reference=payment_reference or None,
                note=notes or None,
            )
            Payment.objects.filter(id=payment.id).update(created_at=voucher_date)

            if invoice.amount and paid_amount >= invoice.amount:
                Invoice.objects.filter(id=invoice.id).update(status="paid")

        messages.success(request, f"Voucher saved as Invoice {invoice.number}.")
        invoice_url = reverse("commerce:invoice_view", kwargs={"invoice_id": invoice.id})
        if submit_action == "print":
            return redirect(f"{invoice_url}?print=1")
        return redirect(invoice_url)

    return render(
        request,
        "commerce/sales_voucher_quick_create.html",
        {"parties": parties, "products": products, "warehouses": warehouses, "initial_party_id": initial_party_id},
    )


@login_required
def sales_voucher_create(request, order_id):
    """
    Legacy URL: keep existing route working and forward to the new query-param flow.
    """
    return redirect(f"{reverse('commerce:sales_voucher_create')}?order_id={int(order_id)}")


@login_required
def sales_voucher_detail(request, invoice_no):
    """
    Voucher detail with print and download options.
    """
    voucher = get_object_or_404(
        SalesVoucher.objects.select_related("party", "order").prefetch_related("items__product", "items__warehouse"),
        invoice_no=invoice_no,
        party__owner=request.user,
    )

    context = {
        "voucher": voucher,
        "print_url": f"/commerce/sales/voucher/{invoice_no}/print/",
        "download_url": f"/commerce/sales/voucher/{invoice_no}/download/",
    }

    return render(request, "commerce/sales_voucher_detail.html", context)


def _get_issuer_profile(user):
    try:
        return UserProfile.objects.filter(user=user).first()
    except Exception:
        return None


@login_required
def sales_voucher_print(request, invoice_no):
    context = _build_sales_voucher_context(request, invoice_no)
    if (request.GET.get("format") or "").lower() == "pdf":
        return _sales_voucher_pdf_response(request, invoice_no, context=context)
    return render(request, "commerce/sales_voucher_print.html", context)


@login_required
def sales_voucher_download(request, invoice_no):
    context = _build_sales_voucher_context(request, invoice_no)
    return _sales_voucher_pdf_response(request, invoice_no, context=context)


def _build_sales_voucher_context(request, invoice_no):
    voucher = get_object_or_404(
        SalesVoucher.objects.select_related("party", "order").prefetch_related("items__product", "items__warehouse"),
        invoice_no=invoice_no,
        party__owner=request.user,
    )
    item_rows = []
    subtotal = Decimal("0.00")
    gst_total = Decimal("0.00")
    for it in voucher.items.all():
        qty = Decimal(str(getattr(it, "qty", 0) or 0))
        rate = Decimal(str(getattr(it, "rate", 0) or 0))
        gst_rate = Decimal(str(getattr(it, "gst_rate", 0) or 0))
        amount = (qty * rate).quantize(Decimal("0.01"))
        gst_amount = (amount * gst_rate / Decimal("100")).quantize(Decimal("0.01")) if voucher.is_gst else Decimal("0.00")
        line_total = (amount + gst_amount).quantize(Decimal("0.01"))

        subtotal += amount
        gst_total += gst_amount
        item_rows.append(
            {
                "product_name": getattr(getattr(it, "product", None), "name", None) or "-",
                "warehouse_name": getattr(getattr(it, "warehouse", None), "name", None) or "",
                "qty": qty,
                "rate": rate,
                "gst_rate": gst_rate,
                "amount": amount,
                "gst_amount": gst_amount,
                "line_total": line_total,
            }
        )

    computed_total = (subtotal + gst_total).quantize(Decimal("0.01"))
    total = (voucher.total_amount or computed_total).quantize(Decimal("0.01"))

    print_url = reverse("commerce:sales_voucher_print", kwargs={"invoice_no": invoice_no})
    download_url = reverse("commerce:sales_voucher_download", kwargs={"invoice_no": invoice_no})
    receipt_pdf_url = ""
    if getattr(voucher, "order", None) and getattr(voucher.order, "invoice", None):
        receipt_pdf_url = (
            reverse("ledger:receipt")
            + f"?reference_type=commerce.Invoice&reference_id={voucher.order.invoice.id}&format=pdf"
        )

    return {
        "voucher": voucher,
        "items": item_rows,
        "party": voucher.party,
        "issuer": _get_issuer_profile(request.user),
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "gst_total": gst_total.quantize(Decimal("0.01")),
        "total": total,
        "print_url": print_url,
        "download_url": download_url,
        "receipt_pdf_url": receipt_pdf_url,
        "hide_sidebar": True,
    }


def _sales_voucher_pdf_response(request, invoice_no, *, context):
    pdf_bytes = render_to_pdf_bytes("commerce/sales_voucher_pdf.html", context, request=request)
    if not pdf_bytes:
        return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

    filename = f"sales_voucher_{invoice_no}.pdf"
    inline = (request.GET.get("inline") or "").strip() == "1"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{filename}"'
    return resp


# ---------------- Invoice ----------------
@login_required
def add_invoice(request):
    """Create invoice for a selected order."""
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot create invoices.")
        return redirect("commerce:invoice_list")

    orders = (
        Order.objects.filter(owner=request.user)
        .select_related("party")
        .order_by("-created_at")
    )
    initial_order_id = (request.GET.get("order") or "").strip()

    if request.method == "POST":
        order_id = request.POST.get("order")
        force_create = (request.POST.get("force_duplicate") or "").strip() == "1"

        if not order_id:
            messages.error(request, "⚠️ Please select an order.")
            return render(request, "commerce/add_invoice.html", {"orders": orders, "initial_order_id": initial_order_id})

        order = get_object_or_404(Order, id=order_id, owner=request.user)

        # Prevent duplicate invoice creation for same order
        if hasattr(order, "invoice"):
            messages.warning(request, "⚠️ Invoice already exists for this order.")
            return redirect("accounts:dashboard")

        try:
            # Smart BI: Festival Sale Mode (auto-discount)
            try:
                from smart_bi.services.festival import apply_festival_discount

                apply_festival_discount(order, day=timezone.localdate(), save=True)
            except Exception:
                pass

            # Smart BI: Duplicate invoice detection (pre-create warning)
            try:
                from smart_bi.models import DuplicateInvoiceSettings
                from smart_bi.services.duplicate_invoices import find_possible_duplicate_invoices

                dup_settings = DuplicateInvoiceSettings.get_for_owner(request.user)
                candidates = find_possible_duplicate_invoices(order=order, settings=dup_settings, max_results=5)
            except Exception:
                candidates = []

            if candidates and not force_create:
                return render(
                    request,
                    "smart_bi/duplicate_invoice_warning.html",
                    {
                        "source": "commerce.add_invoice",
                        "order": order,
                        "new_amount": order.total_amount(),
                        "candidates": candidates,
                        "continue_payload": {"order": str(order.id), "force_duplicate": "1"},
                        "cancel_url": reverse("commerce:add_invoice") + f"?order={order.id}",
                    },
                )

            invoice = Invoice.objects.create(
                order=order,
                gst_type="GST" if (getattr(order, "tax_percent", None) or Decimal("0.00")) > 0 else "NON_GST",
            )

            # Smart BI: log duplicate candidates (post-create)
            try:
                from smart_bi.services.duplicate_invoices import log_possible_duplicates

                if candidates:
                    log_possible_duplicates(
                        owner=request.user,
                        created_by=request.user,
                        invoice=invoice,
                        candidates=candidates,
                    )
            except Exception:
                pass
            messages.success(request, "🧾 Invoice created successfully!")
            return redirect("accounts:dashboard")

        except Exception as e:
            messages.error(request, f"❌ Error creating invoice: {str(e)}")

    return render(request, "commerce/add_invoice.html", {"orders": orders, "initial_order_id": initial_order_id})


@login_required
def invoice_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Invoice.objects.select_related("order", "order__party").filter(order__owner=request.user)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(order__party__name__icontains=q) | Q(order_id__icontains=q))
    if status in {"unpaid", "paid", "cancelled"}:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "invoices": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/invoice_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "commerce/invoice_list.html", context)


@login_required
def voucher_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = (
        Invoice.objects.select_related("order", "order__party")
        .filter(order__owner=request.user, order__order_source__iexact="Voucher")
    )
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(order__party__name__icontains=q) | Q(order_id__icontains=q))
    if status in {"unpaid", "paid", "cancelled"}:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "invoices": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/voucher_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "commerce/voucher_list.html", context)


@login_required
def invoice_view(request, invoice_id):
    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "order__party", "order__warehouse").prefetch_related("payments"),
        id=invoice_id,
        order__owner=request.user,
    )
    items = invoice.order.items.select_related("product").all().order_by("id")
    payments = invoice.payments.all().order_by("-created_at", "-id")
    paid_total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    invoice_amount = invoice.amount or Decimal("0.00")
    balance = invoice_amount - paid_total

    # Portal payment link (shareable Pay Now URL)
    portal_payment_url = ""
    try:
        from portal.models import PaymentLink

        pl = (
            PaymentLink.objects.filter(invoice=invoice)
            .exclude(status__in=[PaymentLink.Status.EXPIRED, PaymentLink.Status.FAILED])
            .order_by("-created_at", "-id")
            .first()
        )
        if not pl and balance > 0:
            import secrets

            # Best-effort unique token generation
            token = secrets.token_hex(32)
            for _ in range(3):
                if not PaymentLink.objects.filter(token=token).exists():
                    break
                token = secrets.token_hex(32)
            pl = PaymentLink.objects.create(
                owner=request.user,
                invoice=invoice,
                token=token,
                amount=invoice_amount,
                status=PaymentLink.Status.CREATED,
                expires_at=timezone.now() + timedelta(days=7),
            )
        if pl:
            portal_payment_url = request.build_absolute_uri(reverse("portal:pay", args=[pl.token]))
    except Exception:
        portal_payment_url = ""
    try:
        from validation.models import FraudAlert  # local import

        alerts = list(
            FraudAlert.objects.filter(
                owner=request.user,
                reference_type="commerce.Invoice",
                reference_id=invoice.id,
                status=FraudAlert.Status.OPEN,
            )
            .order_by("-created_at", "-id")[:10]
        )
    except Exception:
        alerts = []
    return render(
        request,
        "commerce/invoice_view.html",
        {
            "invoice": invoice,
            "items": items,
            "payments": payments,
            "paid_total": paid_total,
            "balance": balance,
            "portal_payment_url": portal_payment_url,
            "smart_alerts": alerts,
            "auto_print": (request.GET.get("print") == "1"),
        },
    )


@login_required
def invoice_print(request, invoice_id):
    invoice = get_object_or_404(Invoice.objects.select_related("order", "order__party"), id=invoice_id, order__owner=request.user)
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
        "issuer": _get_issuer_profile(request.user),
        "hide_sidebar": True,
    }

    if (request.GET.get("format") or "").lower() == "pdf":
        pdf_bytes = render_to_pdf_bytes("commerce/invoice_pdf.html", context, request=request)
        if not pdf_bytes:
            return HttpResponse("PDF renderer unavailable", status=501, content_type="text/plain")

        filename = f"invoice_{invoice.number or invoice.id}.pdf"
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        inline = (request.GET.get("inline") or "").strip() == "1"
        resp["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{filename}"'
        return resp

    return render(request, "commerce/invoice_print.html", context)


# ---------------- Payment ----------------
@login_required
def add_payment(request):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot add payments.")
        return redirect("commerce:payment_list")

    initial_invoice_id = (request.GET.get("invoice_id") or "").strip()
    if request.method == "POST":
        amount = request.POST.get("amount")
        method = request.POST.get("method")
        reference = request.POST.get("reference")
        note = request.POST.get("note")
        invoice_id = request.POST.get("invoice_id")
        payment_date = request.POST.get("payment_date")
        payment_proof = request.FILES.get("payment_proof")
        final_notes = request.POST.get("final_notes")

        try:
            invoice = Invoice.objects.select_related("order").get(id=invoice_id, order__owner=request.user)
        except Invoice.DoesNotExist:
            messages.error(request, "❌ Invalid invoice selected.")
            return redirect("commerce:add_payment")

        # Combine notes
        combined_note = note or ""
        if final_notes:
            combined_note += "\n" + final_notes

        duplicate_payment = Payment.objects.filter(
            invoice=invoice,
            amount=amount,
            method=method or "",
            reference=reference or "",
            is_deleted=False,
        ).first()
        if not duplicate_payment:
            Payment.objects.create(
                invoice=invoice,
                amount=amount,
                method=method,
                reference=reference,
                note=combined_note,
            )
        messages.success(request, "💰 Payment added successfully!")
        return redirect("accounts:dashboard")

    invoices = (
        Invoice.objects.select_related("order", "order__party")
        .filter(order__owner=request.user)
        .order_by("-created_at", "-id")
    )
    return render(request, "commerce/add_payment.html", {"invoices": invoices, "initial_invoice_id": initial_invoice_id})


@login_required
def payment_list(request):
    q = (request.GET.get("q") or "").strip()
    method = (request.GET.get("method") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Payment.objects.select_related("invoice", "invoice__order", "invoice__order__party").filter(
        invoice__order__owner=request.user,
        is_deleted=False,
    )
    if q:
        qs = qs.filter(
            Q(invoice__number__icontains=q)
            | Q(invoice__order__party__name__icontains=q)
            | Q(reference__icontains=q)
            | Q(note__icontains=q)
        )
    if method:
        qs = qs.filter(method__icontains=method)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    context = {
        "payments": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "method": method,
        "date_from": date_from,
        "date_to": date_to,
    }

    if request.GET.get("ajax") == "1":
        rows_html = render_to_string("commerce/partials/payment_list_rows.html", context, request=request)
        pagination_html = render_to_string("core/includes/ajax_pagination.html", {"page_obj": page_obj}, request=request)
        return JsonResponse({"rows_html": rows_html, "pagination_html": pagination_html})

    return render(request, "commerce/payment_list.html", context)


@login_required
def payment_view(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("invoice", "invoice__order", "invoice__order__party"),
        id=payment_id,
        invoice__order__owner=request.user,
        is_deleted=False,
    )
    return render(request, "commerce/payment_view.html", {"payment": payment, "auto_print": (request.GET.get("print") == "1")})


@login_required
def payment_edit(request, payment_id):
    if not erp_can_edit(request.user):
        messages.error(request, "Permission denied: view-only role cannot edit payments.")
        return redirect("commerce:payment_view", payment_id=payment_id)

    payment = get_object_or_404(
        Payment.objects.select_related("invoice", "invoice__order"),
        id=payment_id,
        invoice__order__owner=request.user,
        is_deleted=False,
    )

    if request.method == "POST":
        amount = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip()
        reference = (request.POST.get("reference") or "").strip()
        note = (request.POST.get("note") or "").strip()

        if not amount:
            messages.error(request, "Amount is required.")
            return render(request, "commerce/payment_edit.html", {"payment": payment})

        payment.amount = amount
        payment.method = method
        payment.reference = reference
        payment.note = note
        payment.save(update_fields=["amount", "method", "reference", "note"])
        messages.success(request, "Saved Successfully")
        return redirect("commerce:payment_view", payment_id=payment.id)

    return render(request, "commerce/payment_edit.html", {"payment": payment})


@login_required
def payment_delete(request, payment_id):
    if request.method != "POST":
        return HttpResponse(status=405)

    if not erp_can_delete(request.user):
        messages.error(request, "Permission denied: only Admin can delete.")
        return redirect("commerce:payment_view", payment_id=payment_id)

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        invoice__order__owner=request.user,
    )
    payment.is_deleted = True
    payment.deleted_at = timezone.now()
    payment.save(update_fields=["is_deleted", "deleted_at"])
    messages.success(request, "Saved Successfully")
    return redirect("commerce:payment_list")


# ---------------- Chat ----------------
@login_required
def add_chat_thread(request):
    if request.method == "POST":
        party_id = request.POST.get("party")
        party = get_object_or_404(Party, id=party_id)
        ChatThread.objects.create(party=party)
        messages.success(request, "💬 Chat thread created!")
        return redirect("accounts:dashboard")

    parties = Party.objects.filter(owner=request.user).order_by("name")
    return render(request, "commerce/add_chat_thread.html", {"parties": parties})


@login_required
def add_chat_message(request):
    if request.method == "POST":
        thread_id = request.POST.get("thread")
        text = request.POST.get("text")
        thread = get_object_or_404(ChatThread, id=thread_id, party__owner=request.user)
        ChatMessage.objects.create(thread=thread, message=text, sender=request.user)
        messages.success(request, "📨 Message sent successfully!")
        return redirect("accounts:dashboard")

    threads = ChatThread.objects.select_related("party").filter(party__owner=request.user).order_by("-id")
    return render(request, "commerce/add_chat_message.html", {"threads": threads})

def chat_room(request, thread_id):
    """Show all messages of a specific chat thread."""
    thread = get_object_or_404(ChatThread, id=thread_id)
    messages = ChatMessage.objects.filter(thread=thread).order_by("timestamp")
    return render(request, "commerce/chat_room.html", {
        "thread": thread,
        "messages": messages,
    })

def api_chat_messages(request, thread_id):
    try:
        thread = ChatThread.objects.get(id=thread_id)
        messages = thread.messages.all().values(
            "id", "sent_by", "text", "attachment", "created_at", "is_read"
        )
        return JsonResponse(list(messages), safe=False)
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": "Chat thread not found"}, status=404)


# ---------------- APIs ----------------
@csrf_exempt
@login_required
def api_chat_send(request, thread_id):
    if request.method == "POST":
        thread = get_object_or_404(ChatThread, id=thread_id)
        data = json.loads(request.body.decode("utf-8"))
        message = data.get("message", "").strip()
        if not message:
            return JsonResponse({"error": "Empty message"}, status=400)

        msg = ChatMessage.objects.create(
            thread=thread,
            sender=request.user,
            message=message,
            timestamp=timezone.now()
        )
        return JsonResponse({
            "id": msg.id,
            "sender": msg.sender.username,
            "message": msg.message,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return JsonResponse({"error": "Only POST method allowed"}, status=405)

# ---------------- WhatsApp Orders ----------------
PAYMENT_MODES = {
    "cash": "Cash",
    "paytm": "Paytm",
    "cod": "Cash on Delivery",
    "netbanking": "Netbanking",
}


def _wa_help_text():
    return (
        "Welcome! Quick options (reply text):\n"
        "[products] [cart] [checkout]\n"
        "You can also type:\n"
        "- category <name>\n"
        "- add <qty> <product>\n"
        "- pay cash/paytm/cod/netbanking"
    )


def _wa_categories_text(owner, party):
    categories = Category.objects.filter(owner=owner).order_by("name")
    if not categories.exists():
        categories = Category.objects.all().order_by("name")
    if not categories.exists():
        return "No categories found."

    cat_lines = "\n".join([f"- {c.name}" for c in categories])
    segment = party.customer_category or "General"
    return f"Customer segment: {segment}\nCategories:\n{cat_lines}\nQuick: [category <name>] [cart]"


def _wa_products_in_category(owner, category_name):
    category = Category.objects.filter(owner=owner, name__iexact=category_name).first()
    if not category:
        category = Category.objects.filter(name__iexact=category_name).first()
    if not category:
        return "Category not found. Type 'products' to see categories."

    products = Product.objects.filter(category=category, owner=owner).order_by("name")
    if not products.exists():
        products = Product.objects.filter(category=category).order_by("name")
    if not products.exists():
        return f"No products in {category.name}."

    lines = "\n".join([f"- {p.name} (Rs. {p.price})" for p in products])
    return f"{category.name} products:\n{lines}\nQuick: [add <qty> <product>] [cart]"


def _wa_cart_text(session):
    items = session.cart_items.select_related("product")
    if not items.exists() and not session.unmatched_items:
        return "Your cart is empty. Type 'products' to browse."

    lines = []
    total = Decimal("0.00")
    for item in items:
        line_total = item.quantity * item.unit_price
        total += line_total
        lines.append(f"- {item.product.name} x {item.quantity} = Rs. {line_total}")

    for item in session.unmatched_items:
        lines.append(f"- {item.get('name')} x {item.get('qty')} (manual review)")

    lines.append(f"Total: Rs. {total}")
    lines.append("Type 'checkout' to place order.")
    return "\n".join(lines)


def _wa_strip_verbs(text):
    lower = text.lower().strip()
    for verb in ["add ", "order ", "buy ", "need ", "want "]:
        if lower.startswith(verb):
            return text[len(verb):].strip()
    return text


@login_required
def whatsapp_order_inbox(request):
    status = (request.GET.get("status") or "all").strip().lower()
    q = (request.GET.get("q") or "").strip()

    base_qs = WhatsAppOrderInbox.objects.filter(owner=request.user)
    inbox_qs = base_qs.select_related("party", "order", "whatsapp_account")

    valid_statuses = {choice[0] for choice in WhatsAppOrderInbox.STATUS_CHOICES}
    if status in valid_statuses:
        inbox_qs = inbox_qs.filter(status=status)
    else:
        status = "all"

    if q:
        inbox_qs = inbox_qs.filter(
            Q(customer_name__icontains=q)
            | Q(mobile_number__icontains=q)
            | Q(raw_message__icontains=q)
            | Q(party__name__icontains=q)
        )

    status_counts = {key: base_qs.filter(status=key).count() for key, _label in WhatsAppOrderInbox.STATUS_CHOICES}
    status_counts["all"] = base_qs.count()
    urgent_count = status_counts.get("new", 0) + status_counts.get("manual_review", 0)

    inbox = list(inbox_qs[:200])
    parsed_total = 0
    missing_total = 0
    for entry in inbox:
        items = entry.parsed_items if isinstance(entry.parsed_items, list) else []
        parsed_total += len(items)
        missing_total += sum(1 for item in items if isinstance(item, dict) and not item.get("matched"))

    return render(
        request,
        "commerce/whatsapp_order_inbox.html",
        {
            "inbox": inbox,
            "status_filter": status,
            "q": q,
            "status_counts": status_counts,
            "urgent_count": urgent_count,
            "parsed_total": parsed_total,
            "missing_total": missing_total,
        },
    )


@login_required
@require_POST
def whatsapp_order_action(request, inbox_id, action):
    inbox = get_object_or_404(WhatsAppOrderInbox, id=inbox_id, owner=request.user)
    if action == "approve":
        inbox.status = "approved"
        if inbox.order:
            inbox.order.status = "accepted"
            inbox.order.save(update_fields=["status"])
        inbox.save(update_fields=["status"])
        messages.success(request, f"WhatsApp order #{inbox.id} approved.")
    elif action == "reject":
        inbox.status = "rejected"
        if inbox.order:
            inbox.order.status = "rejected"
            inbox.order.save(update_fields=["status"])
        inbox.save(update_fields=["status"])
        messages.error(request, f"WhatsApp order #{inbox.id} rejected.")
    elif action == "manual":
        inbox.status = "manual_review"
        inbox.save(update_fields=["status"])
        messages.info(request, f"WhatsApp order #{inbox.id} moved to manual review.")
    else:
        messages.error(request, "Invalid action.")
    return redirect("commerce:whatsapp_order_inbox")


@csrf_exempt
@require_POST
def api_whatsapp_order_inbox(request):
    """
    Chatbot intake endpoint for WhatsApp messages.
    Expected JSON:
    {
      "mobile": "9999999999",
      "message": "1 atta, 2 milk",
      "owner_id": 1,
      "customer_name": "Ravi",
      "address": "..."
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    mobile = (payload.get("mobile") or "").strip()
    message = (payload.get("message") or "").strip()
    owner_id = payload.get("owner_id")
    customer_name = (payload.get("customer_name") or "").strip()
    address = (payload.get("address") or "").strip()
    whatsapp_account_id = (payload.get("whatsapp_account_id") or payload.get("account_id") or "").strip()

    if not mobile or not message:
        return JsonResponse({"error": "mobile and message are required"}, status=400)

    party = Party.objects.filter(whatsapp_number=mobile).first() or Party.objects.filter(mobile=mobile).first()
    owner = party.owner if party else None

    if not owner and owner_id:
        owner = User.objects.filter(id=owner_id).first()

    if not owner and request.user.is_authenticated:
        owner = request.user

    if not owner:
        return JsonResponse({"error": "Unable to determine owner for this message"}, status=400)

    wa_account = None
    if whatsapp_account_id:
        try:
            from whatsapp.models import WhatsAppAccount

            wa_account = WhatsAppAccount.objects.filter(id=whatsapp_account_id, owner=owner).first()
        except Exception:
            wa_account = None

    res = handle_whatsapp_order_message(
        owner=owner,
        whatsapp_account=wa_account,
        mobile_number=mobile,
        message=message,
        customer_name=customer_name,
        address=address,
    )
    if not res.ok:
        return JsonResponse({"error": res.reply}, status=400)
    return JsonResponse({"reply": res.reply, "order_id": res.order_id, "invoice_id": res.invoice_id})


@require_GET
def api_orders_live_feed(request):
    owner_id = request.GET.get("owner_id")
    owner = None
    if request.user.is_authenticated:
        owner = request.user
    if not owner and owner_id:
        owner = User.objects.filter(id=owner_id).first()

    if not owner:
        return JsonResponse({"error": "owner not resolved"}, status=400)

    today = timezone.now().date()

    items_subtotal = Sum(
        ExpressionWrapper(F("items__qty") * F("items__price"), output_field=DecimalField(max_digits=14, decimal_places=2))
    )
    base_qs = (
        Order.objects.filter(owner=owner, order_source__iexact="whatsapp")
        .select_related("party")
        .annotate(items_subtotal=items_subtotal)
    )

    orders = base_qs.order_by("-created_at", "-id")[:10]
    total_today = base_qs.filter(created_at__date=today)

    total_today_count = total_today.count()

    total_sales_today = Decimal("0.00")
    for o in total_today:
        subtotal = o.items_subtotal or Decimal("0.00")
        total_sales_today += subtotal - (o.discount_amount or Decimal("0.00")) + (o.tax_amount or Decimal("0.00")) + o.bill_sundry_total()

    data = {
        "total_orders_today": total_today_count,
        "total_sales_today": float(total_sales_today),
        "latest_orders": [
            {
                "id": o.id,
                "order_no": f"#{o.id}",
                "customer_name": o.party.name if o.party else "Unknown",
                "mobile": o.party.mobile if o.party else "",
                "total": float((o.items_subtotal or Decimal("0.00")) - (o.discount_amount or Decimal("0.00")) + (o.tax_amount or Decimal("0.00")) + o.bill_sundry_total()),
                "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for o in orders
        ],
    }
    return JsonResponse(data)

# ---------------- Coupons ----------------
@login_required
def coupon_list(request):
    """Admin view to list all coupons"""
    coupons = Coupon.objects.all().order_by("-created_at")
    return render(request, "commerce/coupon_list.html", {"coupons": coupons})

@login_required
def coupon_create(request):
    """Admin view to create new coupon"""
    if request.method == "POST":
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Coupon created successfully!")
            return redirect("commerce:coupon_list")
    else:
        form = CouponForm()
    return render(request, "commerce/coupon_form.html", {"form": form, "title": "Create Coupon"})

@login_required
def coupon_edit(request, pk):
    """Admin view to edit coupon"""
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == "POST":
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, "Coupon updated successfully!")
            return redirect("commerce:coupon_list")
    else:
        form = CouponForm(instance=coupon)
    return render(request, "commerce/coupon_form.html", {"form": form, "title": "Edit Coupon"})

@login_required
def coupon_delete(request, pk):
    """Admin view to delete coupon"""
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == "POST":
        coupon.delete()
        messages.success(request, "Coupon deleted successfully!")
        return redirect("commerce:coupon_list")
    return render(request, "commerce/coupon_confirm_delete.html", {"coupon": coupon})

@login_required
def user_coupon_list(request):
    """User view to list their coupons"""
    user_coupons = UserCoupon.objects.filter(user=request.user).select_related('coupon')
    return render(request, "commerce/user_coupon_list.html", {"user_coupons": user_coupons})

@login_required
def apply_coupon(request):
    """Apply a coupon to an order or cart"""
    if request.method == "POST":
        code = request.POST.get("code")
        # Implement coupon application logic here
        messages.success(request, f"Coupon {code} applied successfully!")
        return redirect("commerce:user_coupon_list")
    return render(request, "commerce/apply_coupon.html")

@login_required
def spin_wheel(request):
    """Spin the wheel to win a coupon"""
    if request.method == "POST":
        # Simple random win logic
        win = random.choice([True, False])
        if win:
            # Assign a random coupon
            coupon = Coupon.objects.filter(is_active=True).order_by('?').first()
            if coupon:
                UserCoupon.objects.get_or_create(user=request.user, coupon=coupon)
                messages.success(request, f"Congratulations! You won {coupon.title}")
            else:
                messages.info(request, "No coupons available right now.")
        else:
            messages.info(request, "Better luck next time!")
        return redirect("commerce:spin_wheel")
    return render(request, "commerce/spin_wheel.html")

@login_required
def scratch_card(request):
    """Scratch card to win a coupon"""
    if request.method == "POST":
        # Simple random win logic
        win = random.choice([True, False])
        if win:
            coupon = Coupon.objects.filter(is_active=True).order_by('?').first()
            if coupon:
                UserCoupon.objects.get_or_create(user=request.user, coupon=coupon)
                messages.success(request, f"Congratulations! You won {coupon.title}")
            else:
                messages.info(request, "No coupons available right now.")
        else:
            messages.info(request, "Better luck next time!")
        return redirect("commerce:scratch_card")
    return render(request, "commerce/scratch_card.html")

@login_required
def dashboard_with_coupons(request):
    """Dashboard showing coupons and user info"""
    user_coupons = UserCoupon.objects.filter(user=request.user).select_related('coupon')
    available_coupons = Coupon.objects.filter(is_active=True)
    context = {
        "user_coupons": user_coupons,
        "available_coupons": available_coupons,
    }
    return render(request, "commerce/dashboard_with_coupons.html", context)


# ---------------- AI Reorder Planner ----------------
def _parse_budget(request, default=None):
    if default is None:
        from commerce.models import CommerceAISettings
        settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
        default = settings_obj.default_budget
    raw = request.GET.get("budget") or request.POST.get("budget")
    if raw is None:
        return default
    try:
        return Decimal(str(raw))
    except Exception:
        return default


@login_required
@require_GET
def ai_reorder_plan_view(request):
    budget = _parse_budget(request, default=Decimal("50000"))
    from commerce.models import CommerceAISettings
    settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
    target_days = request.GET.get("target_days", settings_obj.default_target_days)
    plan = build_reorder_plan(
        user=request.user,
        budget=budget,
        target_stock_days=target_days,
    )
    context = {
        "plan": plan,
        "budget": budget,
        "target_days": target_days,
    }
    return render(request, "commerce/reorder_plan.html", context)


@login_required
@require_GET
def supplier_po_view(request):
    budget = _parse_budget(request, default=Decimal("50000"))
    from commerce.models import CommerceAISettings
    settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
    target_days = request.GET.get("target_days", settings_obj.default_target_days)
    plan = build_reorder_plan(
        user=request.user,
        budget=budget,
        target_stock_days=target_days,
    )
    return render(request, "commerce/supplier_po.html", {"plan": plan, "budget": budget, "target_days": target_days})


@login_required
@require_GET
def api_ai_reorder_plan(request):
    budget = _parse_budget(request, default=Decimal("50000"))
    from commerce.models import CommerceAISettings
    settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
    target_days = request.GET.get("target_days", settings_obj.default_target_days)
    plan = build_reorder_plan(
        user=request.user,
        budget=budget,
        target_stock_days=target_days,
    )
    return JsonResponse(plan, safe=False)


@login_required
@require_GET
def api_dashboard_reorder_summary(request):
    budget = _parse_budget(request, default=Decimal("50000"))
    from commerce.models import CommerceAISettings
    settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
    target_days = request.GET.get("target_days", settings_obj.default_target_days)
    summary = build_reorder_summary(
        user=request.user,
        budget=budget,
        target_stock_days=target_days,
    )
    return JsonResponse(summary, safe=False)


@require_GET
def api_dashboard_reorder_summary_health(request):
    return JsonResponse({"status": "ok", "service": "dashboard_reorder_summary"})


@require_GET
def api_ai_reorder_plan_health(request):
    return JsonResponse({"status": "ok", "service": "ai_reorder_plan"})


@login_required
@require_POST
def api_ai_generate_po(request):
    budget = _parse_budget(request, default=Decimal("50000"))
    from commerce.models import CommerceAISettings
    settings_obj = CommerceAISettings.objects.first() or CommerceAISettings.objects.create()
    target_days = request.GET.get("target_days", settings_obj.default_target_days)
    plan = build_reorder_plan(
        user=request.user,
        budget=budget,
        target_stock_days=target_days,
    )

    created_orders = []
    supplier_groups = plan.get("supplier_groups", {})

    for group in supplier_groups.values():
        supplier_id = group.get("supplier_id")
        if not supplier_id:
            continue

        items = [i for i in group.get("items", []) if i.get("qty", 0) > 0]
        if not items:
            continue

        order = Order.objects.create(
            owner=request.user,
            party_id=supplier_id,
            order_type="PURCHASE",
            status="pending",
            notes="AI reorder planner auto-generated PO",
        )

        for item in items:
            product = Product.objects.filter(sku=item.get("sku")).first()
            if not product:
                product = Product.objects.filter(name=item.get("product")).first()
            if not product:
                continue

            OrderItem.objects.create(
                order=order,
                product=product,
                qty=item.get("qty", 0),
                price=item.get("unit_cost", 0),
            )

        created_orders.append(order.id)

    return JsonResponse(
        {
            "success": True,
            "created_orders": created_orders,
            "message": "Purchase orders created" if created_orders else "No purchase orders created",
        }
    )
