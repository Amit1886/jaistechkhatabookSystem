from django.urls import path
from . import views

urlpatterns = [

    path("setup/", views.setup_page),

    path("api/qr/", views.qr_api),

    path("api/status/", views.status_api),

    path("api/reconnect/", views.reconnect_api),

]