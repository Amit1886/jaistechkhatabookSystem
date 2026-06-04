from django.urls import path

from smart_khata import api_views


urlpatterns = [
    path("customer-credit-score/", api_views.CustomerCreditScoreAPI.as_view(), name="customer_credit_score"),
    path("reminder/send/", api_views.ReminderSendAPI.as_view(), name="reminder_send"),
    path("reminder/history/", api_views.ReminderHistoryAPI.as_view(), name="reminder_history"),
    path("high-risk-customers/", api_views.HighRiskCustomersAPI.as_view(), name="high_risk_customers"),
]

