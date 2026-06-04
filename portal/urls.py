from django.urls import path

from portal import views

app_name = "portal"

urlpatterns = [
    # Self-service portal (session based)
    path("", views.portal_home, name="home"),
    path("logout/", views.portal_logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),

    path("customer/dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("customer/ecommerce/", views.customer_ecommerce_dashboard, name="customer_ecommerce_dashboard"),
    path("customer/billing/", views.customer_billing_dashboard, name="customer_billing_dashboard"),
    path("supplier/dashboard/", views.supplier_dashboard, name="supplier_dashboard"),
    path("supplier/purchases/", views.supplier_purchases_dashboard, name="supplier_purchases_dashboard"),
    path("supplier/billing/", views.supplier_billing_dashboard, name="supplier_billing_dashboard"),

    # Customer ecommerce
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:product_id>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.portal_order_list, name="order_list"),
    path("orders/<int:order_id>/", views.portal_order_detail, name="order_detail"),
    path("invoices/", views.portal_invoice_list, name="invoice_list"),
    path("invoices/<int:invoice_id>/", views.portal_invoice_detail, name="invoice_detail"),
    path("invoices/<int:invoice_id>/pdf/", views.portal_invoice_pdf, name="invoice_pdf"),
    path("payments/", views.portal_payment_list, name="payment_list"),
    path("reports/", views.portal_reports, name="reports"),

    # Payment links (public)
    path("pay/<str:token>/", views.payment_link_view, name="pay"),
    path("pay/<str:token>/invoice.pdf", views.payment_link_invoice_pdf, name="pay_invoice_pdf"),

    # APIs (token or session)
    path("api/login/", views.api_portal_login, name="api_login"),
    path("api/products/", views.api_products, name="api_products"),
    path("api/cart/", views.api_cart_get, name="api_cart_get"),
    path("api/cart/add/", views.api_cart_add, name="api_cart_add"),
    path("api/cart/update/", views.api_cart_update, name="api_cart_update"),
    path("api/cart/clear/", views.api_cart_clear, name="api_cart_clear"),
    path("api/checkout/", views.api_checkout, name="api_checkout"),
    path("api/orders/", views.api_orders, name="api_orders"),
    path("api/invoices/", views.api_invoices, name="api_invoices"),

    # Management screens (ERP user side)
    path("manage/customers/", views.manage_customers, name="manage_customers"),
    path("manage/suppliers/", views.manage_suppliers, name="manage_suppliers"),
    path("manage/party/<int:party_id>/", views.manage_party_portal, name="manage_party"),
]
