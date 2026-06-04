from django.urls import path

from procurement import api_views
from procurement import automation_api_views


urlpatterns = [
    path("suppliers/", api_views.SuppliersListCreateAPI.as_view(), name="api_suppliers"),
    path("suppliers/<int:pk>/", api_views.SupplierRetrieveUpdateDestroyAPI.as_view(), name="api_supplier_detail"),
    path("supplier-products/", api_views.SupplierProductListCreateAPI.as_view(), name="api_supplier_products"),
    path(
        "supplier-products/<int:pk>/",
        api_views.SupplierProductRetrieveUpdateDestroyAPI.as_view(),
        name="api_supplier_product_detail",
    ),
    path("best-supplier/<int:product_id>/", api_views.BestSupplierAPI.as_view(), name="api_best_supplier"),
    path(
        "supplier-price-history/",
        api_views.SupplierPriceHistoryListAPI.as_view(),
        name="api_supplier_price_history",
    ),
    # Rating (module-internal)
    path("supplier-ratings/upsert/", api_views.SupplierRatingUpsertAPI.as_view(), name="api_supplier_rating_upsert"),

    # ---------------- AR-CSSPS Purchase Automation ----------------
    path("purchase-automation/drafts/", automation_api_views.PurchaseDraftListAPI.as_view(), name="api_purchase_draft_list"),
    path("purchase-automation/drafts/<int:pk>/", automation_api_views.PurchaseDraftRetrieveAPI.as_view(), name="api_purchase_draft_detail"),
    path(
        "purchase-automation/drafts/<int:draft_id>/process/",
        automation_api_views.PurchaseDraftProcessAPI.as_view(),
        name="api_purchase_draft_process",
    ),
    path(
        "purchase-automation/drafts/<int:draft_id>/approve/",
        automation_api_views.PurchaseDraftApproveAPI.as_view(),
        name="api_purchase_draft_approve",
    ),
    path(
        "purchase-automation/capture/ocr-upload/",
        automation_api_views.PurchaseCaptureOCRUploadAPI.as_view(),
        name="api_purchase_capture_ocr",
    ),
    path(
        "purchase-automation/capture/json/",
        automation_api_views.PurchaseCaptureJsonAPI.as_view(),
        name="api_purchase_capture_json",
    ),
    path(
        "purchase-automation/capture/voice/",
        automation_api_views.PurchaseCaptureVoiceAPI.as_view(),
        name="api_purchase_capture_voice",
    ),
    path(
        "purchase-automation/webhooks/whatsapp-invoice/",
        automation_api_views.PurchaseCaptureWhatsAppInvoiceWebhookAPI.as_view(),
        name="api_purchase_whatsapp_invoice_webhook",
    ),
    path(
        "purchase-automation/supplier-api/invoices/",
        automation_api_views.SupplierAPIIngestInvoiceAPI.as_view(),
        name="api_supplier_api_ingest_invoice",
    ),
]
