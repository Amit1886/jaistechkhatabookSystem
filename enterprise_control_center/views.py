from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import date, timedelta
import csv
import json
import logging

logger = logging.getLogger(__name__)


def _superuser_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            return render(request, "403.html", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


@login_required
@staff_member_required
def dashboard_hub(request):
    return render(request, "enterprise_control_center/admin/dashboard_hub.html")


@login_required
@permission_required("rbac.view_branch", raise_exception=True)
def executive_overview(request):
    return render(request, "enterprise_control_center/admin/executive_overview.html")


@login_required
@permission_required("saas.view_department", raise_exception=True)
def business_overview(request):
    return render(request, "enterprise_control_center/admin/business_overview.html")


@login_required
@permission_required("jaistech_erp.view_store", raise_exception=True)
def model_analytics_page(request):
    return render(request, "enterprise_control_center/admin/model_analytics.html")


@login_required
def service_monitoring_page(request):
    return render(request, "enterprise_control_center/admin/service_monitoring.html")


@login_required
def notifications_page(request):
    return render(request, "enterprise_control_center/admin/notifications.html")


@login_required
def heatmaps_page(request):
    return render(request, "enterprise_control_center/admin/heatmaps.html")


@login_required
def timeline_page(request):
    return render(request, "enterprise_control_center/admin/timeline.html")


@login_required
def loyalty_analytics_page(request):
    return render(request, "enterprise_control_center/admin/loyalty_analytics.html")


@login_required
def hr_analytics_page(request):
    return render(request, "enterprise_control_center/admin/hr_analytics.html")


@login_required
def manufacturing_analytics_page(request):
    return render(request, "enterprise_control_center/admin/manufacturing_analytics.html")


@login_required
def online_store_analytics_page(request):
    return render(request, "enterprise_control_center/admin/online_store_analytics.html")


@login_required
@_superuser_required
def companies_page(request):
    return render(request, "enterprise_control_center/admin/companies.html")


@login_required
@_superuser_required
def users_page(request):
    return render(request, "enterprise_control_center/admin/users.html")


@login_required
@_superuser_required
def user_create(request):
    return render(request, "enterprise_control_center/admin/user_create.html")


@login_required
@_superuser_required
def user_profile(request, user_id):
    return render(request, "enterprise_control_center/admin/user_profile.html", {"user_id": user_id})


@login_required
@_superuser_required
def user_360_action(request, user_id):
    return render(request, "enterprise_control_center/admin/user_360.html", {"user_id": user_id})


@login_required
@_superuser_required
def user_communication_queue(request):
    return render(request, "enterprise_control_center/admin/user_communication_queue.html")


@login_required
@_superuser_required
def user_edit(request, user_id):
    return render(request, "enterprise_control_center/admin/user_edit.html", {"user_id": user_id})


@login_required
@_superuser_required
def user_delete(request, user_id):
    return render(request, "enterprise_control_center/admin/user_delete.html", {"user_id": user_id})
