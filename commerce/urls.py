from django.urls import path
from . import views
from .views import (
    sales_voucher_detail,
     )
from . import views_bulk



app_name = "commerce"

urlpatterns = [
    # ------------------- Dashboard -------------------
    path("dashboard/", views.user_commerce_dashboard, name="User_dashboard"),
    path("user-dashboard/", views.user_commerce_dashboard, name="user_commerce_dashboard"),


    # ------------------- Products -------------------
    path("add-category/", views.add_category, name="add_category"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("add-product/", views.add_product, name="add_product"),
    path("products/", views.product_list, name="product_list"),
    path("products/bulk-upload/", views_bulk.product_bulk_upload, name="product_bulk_upload"),
    path("products/sample-csv/", views_bulk.product_sample_csv, name="product_sample_csv"),
    path("products/<int:id>/",views.product_detail,name="product_detail"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # ---------------- PRODUCT MANAGEMENT ----------------
    path("product/add/", views.add_product, name="add_product"),
    path("add-payment/", views.add_payment, name="add_payment"),
    path("add-stock/", views.add_stock, name="add_stock"),


   # ------------------- Warehouses -------------------
    path("add-warehouse/", views.add_warehouse, name="add_warehouse"),
    path("warehouses/", views.warehouse_list, name="warehouse_list"),
    path("warehouses/<int:pk>/", views.warehouse_view, name="warehouse_view"),
    path("warehouses/new/", views.warehouse_create, name="warehouse_create"),
    path("warehouses/<int:pk>/edit/", views.warehouse_edit, name="warehouse_edit"),
    path("warehouses/<int:pk>/delete/", views.warehouse_delete, name="warehouse_delete"),

    # ------------------- Orders -------------------
    path("add-order/", views.add_order, name="add_order"),
    # New flow alias: Quotation -> Order
    path("sales/order/create/", views.add_order, name="sales_order_create"),
    path("view-order/<int:order_id>/", views.view_order, name="view_order"),
    path("get-price/<int:pk>/", views.get_product_price, name="get_price"),
    path("api/product-stock/<int:product_id>/", views.get_product_stock, name="get_product_stock"),
    path('download-invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),
    path("orders/", views.order_list, name="order_list"),
    path('orders/sales/', views.sales_order_list, name='sales_order_list'),
    path('orders/sales/<int:order_id>/', views.sales_order_detail, name='sales_order_detail'),
    path('orders/purchase/', views.purchase_order_list, name='purchase_order_list'),
    path("orders/<int:order_id>/<str:action>/",views.order_action,name="order_action"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    # ------------------- Quotations -------------------
    path("quotations/", views.QuotationListView.as_view(), name="quotation_list"),
    path("quotations/create/", views.QuotationCreateView.as_view(), name="quotation_create"),
    path("quotations/<int:pk>/", views.QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/<int:pk>/edit/", views.QuotationUpdateView.as_view(), name="quotation_edit"),
    path("quotations/<int:pk>/<str:action>/", views.quotation_action, name="quotation_action"),
    # Sales voucher (order -> voucher conversion)
    path("sales/voucher/create/", views.SalesVoucherCreateView.as_view(), name="sales_voucher_create"),
    # Legacy route kept for old deep-links
    path("sales/voucher/create/<int:order_id>/", views.sales_voucher_create, name="sales_voucher_create_legacy"),
    # Busy/Tally-style blank voucher entry grid (creates Order + Invoice)
    path("sales/voucher/entry/", views.sales_voucher_quick_create, name="sales_voucher_quick_create"),
    path("sales/voucher/list/", views.voucher_list, name="voucher_list"),
    path("sales/voucher/<int:invoice_no>/", sales_voucher_detail, name="sales_voucher_detail"),
    path("sales/voucher/<int:invoice_no>/print/", views.sales_voucher_print, name="sales_voucher_print"),
    path("sales/voucher/<int:invoice_no>/download/", views.sales_voucher_download, name="sales_voucher_download"),
    path("invoices/add/", views.add_invoice, name="add_invoice"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:invoice_id>/", views.invoice_view, name="invoice_view"),
    path("invoices/<int:invoice_id>/print/", views.invoice_print, name="invoice_print"),
    path("payments/", views.payment_list, name="payment_list"),
    path("payments/bulk-upload/", views_bulk.payment_bulk_upload, name="payment_bulk_upload"),
    path("payments/sample-csv/", views_bulk.payment_sample_csv, name="payment_sample_csv"),
    path("payments/<int:payment_id>/", views.payment_view, name="payment_view"),
    path("payments/<int:payment_id>/edit/", views.payment_edit, name="payment_edit"),
    path("payments/<int:payment_id>/delete/", views.payment_delete, name="payment_delete"),

    # ------------------- WhatsApp Orders -------------------
    path("whatsapp/inbox/", views.whatsapp_order_inbox, name="whatsapp_order_inbox"),
    path("whatsapp/inbox/<int:inbox_id>/<str:action>/", views.whatsapp_order_action, name="whatsapp_order_action"),

    # ------------------- Chat -------------------
    path("add-chat-thread/", views.add_chat_thread, name="add_chat_thread"),
    path("add-chat-message/", views.add_chat_message, name="add_chat_message"),
    path("chat/<int:thread_id>/", views.chat_room, name="chat_room"),
    path("api/chat/<int:thread_id>/messages/", views.api_chat_messages, name="api_chat_messages"),
    path("api/chat/<int:thread_id>/send/", views.api_chat_send, name="api_chat_send"),

    # ------------------- Coupons -------------------
    path("coupons/", views.coupon_list, name="coupon_list"),
    path("coupons/create/", views.coupon_create, name="coupon_create"),
    path("coupons/<int:pk>/edit/", views.coupon_edit, name="coupon_edit"),
    path("coupons/<int:pk>/delete/", views.coupon_delete, name="coupon_delete"),
    path("user-coupons/", views.user_coupon_list, name="user_coupon_list"),
    path("apply-coupon/", views.apply_coupon, name="apply_coupon"),
    path("spin-wheel/", views.spin_wheel, name="spin_wheel"),
    path("scratch-card/", views.scratch_card, name="scratch_card"),
    path("dashboard-with-coupons/", views.dashboard_with_coupons, name="dashboard_with_coupons"),


    # ------------------- AI Reorder Planner -------------------
    path("ai/reorder-plan/", views.ai_reorder_plan_view, name="ai_reorder_plan"),
    path("ai/supplier-po/", views.supplier_po_view, name="supplier_po"),



   ]
