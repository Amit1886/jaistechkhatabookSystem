from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.roles import can_delete as erp_can_delete, can_edit as erp_can_edit
from .forms import AutoDiscountSettingsForm, SlabFormSet, slabs_from_formset
from .models import AppSettings, Customer, Product
from .utils import calculate_auto_discount


def _staff_required(user) -> bool:
    # ERP permission: allow typical owners/admins even if they are not Django-staff.
    return bool(erp_can_edit(user))


@login_required
@user_passes_test(_staff_required)
def billing_page(request: HttpRequest):
    """
    Demo billing page showing live auto-discount calculation.

    Production usage:
    - Integrate this calculation into your invoice/order creation flow.
    - Always recompute final price server-side before saving.
    """
    customers = Customer.objects.filter(is_active=True).order_by("name", "id")[:500]
    products = Product.objects.filter(is_active=True).order_by("name", "id")[:500]
    return render(request, "auto_discount/billing.html", {"customers": customers, "products": products})


@login_required
@user_passes_test(lambda u: bool(erp_can_delete(u)))
def settings_page(request: HttpRequest):
    """
    ERP-side settings UI (non-superadmin) for auto discount engine.
    Only admin-level ERP users can edit.
    """
    settings = AppSettings.get_solo()

    initial_settings = {
        "enable_auto_discount": bool(getattr(settings, "enable_auto_discount", True)),
        "min_profit_percentage": getattr(settings, "min_profit_percentage", 10),
    }

    def _slab_initial(slabs):
        rows = []
        for s in slabs or []:
            try:
                rows.append({"min_qty": int(s.get("min_qty")), "discount": s.get("discount")})
            except Exception:
                continue
        return rows

    if request.method == "POST":
        form = AutoDiscountSettingsForm(request.POST)
        b2b_fs = SlabFormSet(request.POST, prefix="b2b")
        b2c_fs = SlabFormSet(request.POST, prefix="b2c")

        if form.is_valid() and b2b_fs.is_valid() and b2c_fs.is_valid():
            settings.enable_auto_discount = bool(form.cleaned_data.get("enable_auto_discount"))
            settings.min_profit_percentage = float(form.cleaned_data.get("min_profit_percentage") or 0)
            settings.b2b_slabs = slabs_from_formset(b2b_fs)
            settings.b2c_slabs = slabs_from_formset(b2c_fs)
            settings.full_clean()
            settings.save()
            messages.success(request, "Settings save ho gayi.")
            return redirect("auto_discount:settings_page")
        messages.error(request, "Form me error hai. Please check karke dubara save karein.")
    else:
        form = AutoDiscountSettingsForm(initial=initial_settings)
        b2b_fs = SlabFormSet(prefix="b2b", initial=_slab_initial(settings.b2b_slabs))
        b2c_fs = SlabFormSet(prefix="b2c", initial=_slab_initial(settings.b2c_slabs))

    return render(request, "auto_discount/settings.html", {"form": form, "b2b_fs": b2b_fs, "b2c_fs": b2c_fs})


@require_GET
@login_required
@user_passes_test(_staff_required)
def ajax_calculate_discount(request: HttpRequest):
    """
    AJAX API:
      /ajax/calculate-discount/?product_id=1&qty=10&customer_id=2

    Returns:
      - final_price (unit)
      - applied_discount (%)
      - is_adjusted
      - minimum_profit_price (unit)
      - base_selling_price (unit)
    """
    product_id = request.GET.get("product_id")
    qty_raw = request.GET.get("qty")
    customer_id = request.GET.get("customer_id")

    try:
        qty = int(qty_raw or 0)
    except Exception:
        qty = 0
    if qty < 0:
        qty = 0

    product = get_object_or_404(Product, id=product_id, is_active=True)
    customer = get_object_or_404(Customer, id=customer_id, is_active=True)

    res = calculate_auto_discount(product=product, qty=qty, customer_type=customer.customer_type)

    # Profit indicator helpers
    base = Decimal(str(product.selling_price or 0))
    final_price = Decimal(str(res.final_price or 0))
    min_price = Decimal(str(res.minimum_profit_price or 0))
    profit_safe = final_price >= min_price
    near_limit = profit_safe and (final_price - min_price) <= (min_price * Decimal("0.02"))  # within 2%

    return JsonResponse(
        {
            "ok": True,
            "final_price": str(res.final_price),
            "applied_discount": str(res.applied_discount),
            "is_adjusted": bool(res.is_adjusted),
            "minimum_profit_price": str(res.minimum_profit_price),
            "base_selling_price": str(base),
            "profit_safe": bool(profit_safe),
            "near_limit": bool(near_limit),
        }
    )
