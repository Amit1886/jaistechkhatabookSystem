from django.urls import path

from smart_khata import views


app_name = "smart_khata"

urlpatterns = [
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:party_id>/", views.customer_profile, name="customer_profile"),
    path("credit-scores/", views.credit_score_dashboard, name="credit_score_dashboard"),
    path("reminders/settings/", views.khata_reminder_settings, name="khata_reminder_settings"),
    path("reminders/logs/", views.reminder_logs, name="reminder_logs"),
    # Reports
    path("reports/credit-ranking/", views.report_credit_ranking, name="report_credit_ranking"),
    path("reports/late-payments/", views.report_late_payments, name="report_late_payments"),
    path("reports/reminder-activity/", views.report_reminder_activity, name="report_reminder_activity"),
    path("reports/high-risk/", views.report_high_risk_customers, name="report_high_risk_customers"),
]
