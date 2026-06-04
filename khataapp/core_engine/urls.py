from django.urls import path

from khataapp.core_engine import views
from khataapp.core_engine.admin_panels import views as admin_views


app_name = "central_engine"


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("rewards/", views.rewards_wallet, name="rewards_wallet"),
    path("referrals/", views.referral_center, name="referral_center"),
    path("loyalty/", views.loyalty_offers, name="loyalty_offers"),
    path("payment-earnings/", views.payment_earnings, name="payment_earnings"),
    path("tasks/", views.task_center, name="task_center"),
    path("tasks/complete/", views.complete_task_view, name="task_complete"),
    path("analytics/", views.analytics_snapshot, name="analytics_snapshot"),
    path("features/", views.feature_unlock_panel, name="feature_unlock_panel"),
    path("profit-preview/", views.profit_preview, name="profit_preview"),
    # Admin control panel (staff only)
    path("admin/", admin_views.control_center, name="admin_control_center"),
    path("admin/logs/", admin_views.logs_audit, name="admin_logs"),
]

