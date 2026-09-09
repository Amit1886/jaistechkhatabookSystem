from django.urls import path
from companies.views import (
    company_create,
    company_detail,
    company_edit,
    company_delete,
)
from . import views

app_name = "enterprise_control_center"

urlpatterns = [
    path("enterprise-dashboard-hub", views.dashboard_hub, name="dashboard_hub"),
    path("executive-overview/", views.executive_overview, name="executive_overview"),
    path("business-overview/", views.business_overview, name="business_overview"),
    path("model-analytics/", views.model_analytics_page, name="model_analytics_page"),
    path("service-monitoring/", views.service_monitoring_page, name="service_monitoring_page"),
    path("notifications/", views.notifications_page, name="notifications_page"),
    path("heatmaps/", views.heatmaps_page, name="heatmaps_page"),
    path("timeline/", views.timeline_page, name="timeline_page"),
    path("loyalty/", views.loyalty_analytics_page, name="loyalty_analytics_page"),
    path("hr/", views.hr_analytics_page, name="hr_analytics_page"),
    path("manufacturing/", views.manufacturing_analytics_page, name="manufacturing_analytics_page"),
    path("online-store/", views.online_store_analytics_page, name="online_store_analytics_page"),
    path("companies/", views.companies_page, name="companies_page"),
    path("companies/create/", company_create, name="company_create"),
    path("companies/<int:pk>/", company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", company_edit, name="company_edit"),
    path("companies/<int:pk>/delete/", company_delete, name="company_delete"),
    path("users/", views.users_page, name="users_page"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:user_id>/", views.user_profile, name="user_profile"),
    path("users/<int:user_id>/360/", views.user_360_action, name="user_360_action"),
    path("users/communication-queue/", views.user_communication_queue, name="user_communication_queue"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),
]
