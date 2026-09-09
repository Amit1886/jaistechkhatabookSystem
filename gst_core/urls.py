from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import (
    GSTRegistrationViewSet,
    GSTCategoryViewSet,
    GSTTransactionViewSet,
)
from . import views

router = DefaultRouter()
router.register(r"registrations", GSTRegistrationViewSet, basename="gst-registration")
router.register(r"categories", GSTCategoryViewSet, basename="gst-category")
router.register(r"transactions", GSTTransactionViewSet, basename="gst-transaction")

app_name = "gst_core"

urlpatterns = [
    path("", include(router.urls)),
    path("web/", views.gst_html_view, name="gst-ui"),
    path("web/registrations/", views.gst_registrations_html_view, name="gst-registrations-ui"),
    path("web/transactions/", views.gst_transactions_html_view, name="gst-transactions-ui"),
    path("hsn/", views.hsn_list, name="hsn_list"),
    path("hsn/add/", views.hsn_create, name="hsn_create"),
    path("hsn/<int:pk>/edit/", views.hsn_edit, name="hsn_edit"),
    path("hsn/<int:pk>/delete/", views.hsn_delete, name="hsn_delete"),
    path("fiscal-year/", views.fiscal_year_list, name="fiscal_year_list"),
    path("fiscal-year/add/", views.fiscal_year_create, name="fiscal_year_create"),
    path("fiscal-year/<int:pk>/edit/", views.fiscal_year_edit, name="fiscal_year_edit"),
    path("fiscal-year/<int:pk>/delete/", views.fiscal_year_delete, name="fiscal_year_delete"),
    path("fiscal-period/", views.fiscal_period_list, name="fiscal_period_list"),
    path("fiscal-period/add/", views.fiscal_period_create, name="fiscal_period_create"),
    path("fiscal-period/<int:pk>/edit/", views.fiscal_period_edit, name="fiscal_period_edit"),
    path("fiscal-period/<int:pk>/delete/", views.fiscal_period_delete, name="fiscal_period_delete"),
    path("gstr1/", views.gstr1_list, name="gstr1_list"),
    path("gstr1/create/", views.gstr1_create, name="gstr1_create"),
    path("gstr1/<int:pk>/", views.gstr1_detail, name="gstr1_detail"),
    path("gstr1/<int:pk>/file/", views.gstr1_filing, name="gstr1_filing"),
    path("gstr1/<int:pk>/cancel/", views.gstr1_cancel, name="gstr1_cancel"),
    path("gstr3b/", views.gstr3b_list, name="gstr3b_list"),
    path("gstr3b/create/", views.gstr3b_create, name="gstr3b_create"),
    path("gstr3b/<int:pk>/", views.gstr3b_detail, name="gstr3b_detail"),
    path("gstr3b/<int:pk>/file/", views.gstr3b_filing, name="gstr3b_filing"),
    path("gstr3b/<int:pk>/cancel/", views.gstr3b_cancel, name="gstr3b_cancel"),
]
