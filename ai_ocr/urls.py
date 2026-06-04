from django.urls import path

from ai_ocr import views

app_name = "ai_ocr"

urlpatterns = [
    path("", views.ocr_invoice_dashboard, name="dashboard"),
]

