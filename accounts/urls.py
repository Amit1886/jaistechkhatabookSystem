# accounts/urls.py
from django.urls import path
from . import views   # <-- sirf apna views kaam aa raha hai
from .views import daily_summary_view


app_name = "accounts"

urlpatterns = [
    path("role-dashboard/", views.role_dashboard, name="role_dashboard"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("party-dashboard/", views.party_dashboard, name="party_dashboard"),
    path("collector-dashboard/", views.collector_dashboard, name="collector_dashboard"),
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("profile/", views.profile_settings, name="profile_settings"),
    path("signup/", views.signup_view, name="signup"),
    path("agent-signup/", views.agent_signup_view, name="agent_signup"),
    path("login/", views.login_view, name="login"),
    path("login-link/<str:token>/", views.login_link_view, name="login_link"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.profile_settings, name="profile_settings"),
    path("subscribe-plan/<int:plan_id>/", views.subscribe_plan, name="subscribe_plan"),
    path('dashboard/edit/', views.edit_profile, name='edit_profile'),
    path("party/<int:party_id>/ledger/", views.party_ledger, name="party_ledger"),
    path('ledger/<int:party_id>/load-more/', views.party_ledger_load_more, name='party_ledger_load_more'),
    path("ledger/", views.ledger_list, name="ledger_list"),
    path("ledger/ui/", views.ledger_ui, name="ledger_ui"),
    path('ledger/<int:party_id>/pdf/', views.party_ledger_pdf, name='party_ledger_pdf'),
    path("summary/", daily_summary_view, name="daily_summary"),
    path("business-snapshot/",views.business_snapshot_view,name="business_snapshot"),
    path("loyalty/", views.loyalty_dashboard, name="loyalty_dashboard"),
    path("expenses/create/", views.create_expense, name="expense_create"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("redeem-points/", views.redeem_points, name="redeem_points"), 
    path("api/billing-hierarchy/", views.api_billing_hierarchy, name="api_billing_hierarchy"),
]

