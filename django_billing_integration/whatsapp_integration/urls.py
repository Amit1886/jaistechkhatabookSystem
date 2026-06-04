from __future__ import annotations

from django.urls import path

from whatsapp_integration import views

app_name = "whatsapp_integration"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("webhook/incoming/", views.webhook_incoming, name="webhook_incoming"),
]

