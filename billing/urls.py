# full path: ~/myproject/khatapro/billing/urls.py

from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    # Plan selection and dashboard
    path("dashboard/", views.dashboard, name="dashboard"),                  # /billing/dashboard/
    path("commerce-dashboard/", views.commerce_dashboard, name="commerce_dashboard"),

    # Linked user management (Billing Dashboard)
    path("users/", views.users_manage, name="users_manage"),
    path("users/create/", views.users_create, name="users_create"),
    path("users/<int:user_id>/edit/", views.users_edit, name="users_edit"),
    path("impersonate/stop/", views.impersonate_stop, name="impersonate_stop"),

    # Payment related
    path("payment-success/<int:plan_id>/", views.payment_success, name="payment-success"),
    path("checkout/", views.checkout, name="checkout"),
    path("public-checkout/", views.public_checkout, name="public-checkout"),
    path("razorpay/verify/", views.razorpay_verify, name="razorpay-verify"),
    path("choose-plan/", views.choose_plan, name="choose_plan"),
    path("upgrade/", views.upgrade_plan, name="upgrade_plan"),
    path("plan-management/", views.plan_management, name="plan_management"),
    path("upgrade/start/<int:plan_id>/", views.start_upgrade, name="start_upgrade"),
    path("history/", views.billing_history, name="billing_history"),

    # Admin feature matrix
    path("admin/feature-matrix/", views.feature_matrix, name="feature_matrix"),
    path("admin/feature-matrix/save/", views.feature_matrix_save, name="feature_matrix_save"),



    # Webhook handlers (for gateways like Razorpay, PhonePe, Paytm etc.)
    #path("webhook/<str:provider>/", views.gateway_webhook, name="gateway_webhook"),
]
