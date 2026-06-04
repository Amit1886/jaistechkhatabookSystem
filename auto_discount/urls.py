from django.urls import path

from . import views

app_name = "auto_discount"

urlpatterns = [
    path("auto-discount/settings/", views.settings_page, name="settings_page"),
    path("auto-discount/billing/", views.billing_page, name="billing_page"),
    path("ajax/calculate-discount/", views.ajax_calculate_discount, name="ajax_calculate_discount"),
]
