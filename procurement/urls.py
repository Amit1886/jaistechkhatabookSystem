from django.urls import path

from procurement import views


app_name = "procurement"

urlpatterns = [
    # Admin/User supplier management (tenant-scoped)
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/add/", views.supplier_add, name="supplier_add"),
    path("suppliers/<int:supplier_id>/edit/", views.supplier_edit, name="supplier_edit"),
    path("suppliers/<int:supplier_id>/delete/", views.supplier_delete, name="supplier_delete"),

    # Mapping + upload
    path("supplier-products/", views.supplier_product_mapping, name="supplier_product_mapping"),

    # User comparison
    path("compare/", views.supplier_price_comparison, name="supplier_price_comparison"),

    # Alerts
    path("alerts/<int:alert_id>/read/", views.mark_alert_read, name="mark_alert_read"),

    # Helpers
    path("api/low-stock-best/", views.api_low_stock_best_suppliers, name="api_low_stock_best"),
    path("api/send-whatsapp-order/", views.api_send_whatsapp_order, name="api_send_whatsapp_order"),
]

