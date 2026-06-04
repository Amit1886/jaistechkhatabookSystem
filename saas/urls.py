from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path("rbac/", views.rbac_registry_view, name="saas-rbac-registry"),
    path("tenant/create/", views.tenant_create_view, name="saas-tenant-create"),
]

