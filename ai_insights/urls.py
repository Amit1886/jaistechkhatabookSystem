from django.urls import path

from ai_insights import views

app_name = "ai_insights"

urlpatterns = [
    path("", views.insights_dashboard, name="dashboard"),
]

