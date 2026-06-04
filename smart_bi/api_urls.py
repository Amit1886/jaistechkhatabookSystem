from django.urls import path

from smart_bi import api_views


urlpatterns = [
    path("check-duplicate-invoice/", api_views.api_check_duplicate_invoice, name="api_check_duplicate_invoice"),
    path("business-health/", api_views.api_business_health, name="api_business_health"),
    path("festival-active/", api_views.api_festival_active, name="api_festival_active"),
    path("festival-sales/", api_views.api_festival_sales, name="api_festival_sales"),
]

