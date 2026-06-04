from django.urls import path

from validation import views

app_name = "validation"

urlpatterns = [
    path("", views.smart_alerts_dashboard, name="dashboard"),
    path("<int:alert_id>/<str:action>/", views.smart_alert_action, name="action"),
]

