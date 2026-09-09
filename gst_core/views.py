from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from .models import GSTRegistration, GSTCategory, GSTTransaction


@login_required
def gst_html_view(request):
    return render(request, "gst_core/gst_dashboard.html")


@login_required
def gst_registrations_html_view(request):
    registrations = GSTRegistration.objects.filter(business=request.user)
    return render(request, "gst_core/registrations.html", {"registrations": registrations})


@login_required
def gst_transactions_html_view(request):
    transactions = GSTTransaction.objects.filter(registration__business=request.user)
    return render(request, "gst_core/transactions.html", {"transactions": transactions})


@login_required
def hsn_list(request):
    categories = GSTCategory.objects.filter(is_active=True)
    return render(request, "gst_core/hsn_list.html", {"categories": categories})


@login_required
def hsn_create(request):
    if request.method == "POST":
        form = GSTCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "HSN/SAC created successfully.")
            return redirect("gst_core:hsn_list")
    else:
        form = GSTCategoryForm()
    return render(request, "gst_core/hsn_form.html", {"form": form})


@login_required
def hsn_edit(request, pk):
    category = get_object_or_404(GSTCategory, pk=pk)
    if request.method == "POST":
        form = GSTCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "HSN/SAC updated successfully.")
            return redirect("gst_core:hsn_list")
    else:
        form = GSTCategoryForm(instance=category)
    return render(request, "gst_core/hsn_form.html", {"form": form, "category": category})


@login_required
def hsn_delete(request, pk):
    category = get_object_or_404(GSTCategory, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "HSN/SAC deleted successfully.")
    return redirect("gst_core:hsn_list")


@login_required
def fiscal_year_list(request):
    return render(request, "gst_core/fiscal_year_list.html")


@login_required
def fiscal_year_create(request):
    if request.method == "POST":
        form = FiscalYearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiscal year created successfully.")
            return redirect("gst_core:fiscal_year_list")
    else:
        form = FiscalYearForm()
    return render(request, "gst_core/fiscal_year_form.html", {"form": form})


@login_required
def fiscal_year_edit(request, pk):
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    if request.method == "POST":
        form = FiscalYearForm(request.POST, instance=fiscal_year)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiscal year updated successfully.")
            return redirect("gst_core:fiscal_year_list")
    else:
        form = FiscalYearForm(instance=fiscal_year)
    return render(request, "gst_core/fiscal_year_form.html", {"form": form, "fiscal_year": fiscal_year})


@login_required
def fiscal_year_delete(request, pk):
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    if request.method == "POST":
        fiscal_year.delete()
        messages.success(request, "Fiscal year deleted successfully.")
    return redirect("gst_core:fiscal_year_list")


@login_required
def fiscal_period_list(request):
    return render(request, "gst_core/fiscal_period_list.html")


@login_required
def fiscal_period_create(request):
    if request.method == "POST":
        form = FiscalPeriodForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiscal period created successfully.")
            return redirect("gst_core:fiscal_period_list")
    else:
        form = FiscalPeriodForm()
    return render(request, "gst_core/fiscal_period_form.html", {"form": form})


@login_required
def fiscal_period_edit(request, pk):
    period = get_object_or_404(FiscalPeriod, pk=pk)
    if request.method == "POST":
        form = FiscalPeriodForm(request.POST, instance=period)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiscal period updated successfully.")
            return redirect("gst_core:fiscal_period_list")
    else:
        form = FiscalPeriodForm(instance=period)
    return render(request, "gst_core/fiscal_period_form.html", {"form": form, "period": period})


@login_required
def fiscal_period_delete(request, pk):
    period = get_object_or_404(FiscalPeriod, pk=pk)
    if request.method == "POST":
        period.delete()
        messages.success(request, "Fiscal period deleted successfully.")
    return redirect("gst_core:fiscal_period_list")


@login_required
def gstr1_list(request):
    return render(request, "gst_core/gstr1_list.html")


@login_required
def gstr1_create(request):
    if request.method == "POST":
        form = GSTR1Form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "GSTR-1 created successfully.")
            return redirect("gst_core:gstr1_list")
    else:
        form = GSTR1Form()
    return render(request, "gst_core/gstr1_form.html", {"form": form})


@login_required
def gstr1_detail(request, pk):
    gstr1 = get_object_or_404(GSTR1, pk=pk)
    return render(request, "gst_core/gstr1_detail.html", {"gstr1": gstr1})


@login_required
def gstr1_filing(request, pk):
    gstr1 = get_object_or_404(GSTR1, pk=pk)
    if request.method == "POST":
        gstr1.status = "filed"
        gstr1.save()
        messages.success(request, "GSTR-1 filed successfully.")
    return redirect("gst_core:gstr1_detail", pk=pk)


@login_required
def gstr1_cancel(request, pk):
    gstr1 = get_object_or_404(GSTR1, pk=pk)
    if request.method == "POST":
        gstr1.status = "cancelled"
        gstr1.save()
        messages.success(request, "GSTR-1 cancelled successfully.")
    return redirect("gst_core:gstr1_list")


@login_required
def gstr3b_list(request):
    return render(request, "gst_core/gstr3b_list.html")


@login_required
def gstr3b_create(request):
    if request.method == "POST":
        form = GSTR3BForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "GSTR-3B created successfully.")
            return redirect("gst_core:gstr3b_list")
    else:
        form = GSTR3BForm()
    return render(request, "gst_core/gstr3b_form.html", {"form": form})


@login_required
def gstr3b_detail(request, pk):
    gstr3b = get_object_or_404(GSTR3B, pk=pk)
    return render(request, "gst_core/gstr3b_detail.html", {"gstr3b": gstr3b})


@login_required
def gstr3b_filing(request, pk):
    gstr3b = get_object_or_404(GSTR3B, pk=pk)
    if request.method == "POST":
        gstr3b.status = "filed"
        gstr3b.save()
        messages.success(request, "GSTR-3B filed successfully.")
    return redirect("gst_core:gstr3b_detail", pk=pk)


@login_required
def gstr3b_cancel(request, pk):
    gstr3b = get_object_or_404(GSTR3B, pk=pk)
    if request.method == "POST":
        gstr3b.status = "cancelled"
        gstr3b.save()
        messages.success(request, "GSTR-3B cancelled successfully.")
    return redirect("gst_core:gstr3b_list")
