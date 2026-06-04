from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .forms import AutoSMSToggleForm
from .models import SMSLog, SMSTemplate


def _get_company_settings():
    from khataapp.models import CompanySettings

    cs = CompanySettings.objects.first()
    if cs is None:
        cs = CompanySettings.objects.create()
    return cs


@login_required
def sms_dashboard(request):
    company = _get_company_settings()
    initial = {"auto_sms_send": bool(getattr(company, "auto_sms_send", True))} if company else {"auto_sms_send": True}

    if request.method == "POST":
        form = AutoSMSToggleForm(request.POST)
        if form.is_valid():
            company.auto_sms_send = form.cleaned_data["auto_sms_send"]
            company.save(update_fields=["auto_sms_send"])
            messages.success(request, "Auto SMS setting updated.")
            return redirect("sms_center:dashboard")
    else:
        form = AutoSMSToggleForm(initial=initial)

    templates = SMSTemplate.objects.all().order_by("template_type", "-enabled", "title")
    logs_qs = SMSLog.objects.select_related("template").all().order_by("-timestamp")
    paginator = Paginator(logs_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "sms_center/dashboard.html",
        {
            "form": form,
            "company": company,
            "templates": templates,
            "page_obj": page_obj,
        },
    )
