from django.urls import path

from smart_bi import views


app_name = "smart_bi"


urlpatterns = [
    path("", views.smart_bi_dashboard, name="dashboard"),
    path("business-health/", views.business_health_dashboard, name="business_health_dashboard"),
    path("festival-campaigns/", views.festival_campaign_list, name="festival_campaign_list"),
    path("festival-campaigns/create/", views.festival_campaign_create, name="festival_campaign_create"),
    path("festival-campaigns/<int:campaign_id>/action/", views.festival_campaign_action, name="festival_campaign_action"),
    path("reports/festival-sales/", views.festival_sales_report, name="festival_sales_report"),
    path("reports/duplicate-invoices/", views.duplicate_invoice_report, name="duplicate_invoice_report"),
    path("settings/duplicate-invoices/", views.duplicate_invoice_settings, name="duplicate_invoice_settings"),
]
