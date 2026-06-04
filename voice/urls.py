from django.urls import path

from voice import views

app_name = "voice"

urlpatterns = [
    path("", views.voice_dashboard, name="dashboard"),
]

