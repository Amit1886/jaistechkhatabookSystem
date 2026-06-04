from django.urls import path

from bank_import import views

app_name = "bank_import"

urlpatterns = [
    path("", views.bank_statement_import, name="import"),
]
