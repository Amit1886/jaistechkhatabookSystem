from django.urls import path

from . import views

app_name = "sms_center"

urlpatterns = [
    path("", views.sms_dashboard, name="dashboard"),
]

