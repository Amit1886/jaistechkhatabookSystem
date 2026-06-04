from django.urls import path
from .views import (
    app_home,
    enterprise_dashboard,
    enterprise_app_bootstrap,
    enterprise_parties,
    enterprise_customers,
    enterprise_customer_detail,
    enterprise_products,
    enterprise_product_detail,
    enterprise_invoices,
    enterprise_transactions,
    login_api,
    mobile_sync_pull,
    mobile_sync_push,
    api_start_ai_call,
    api_generate_qr,
    api_add_shop,
    # New Flutter API endpoints
    api_user_profile,
    api_user_permissions,
    api_dashboard_data,
    api_inventory_products,
    api_billing_invoices,
    api_crm_parties,
    api_transactions_list,
    public_demo_login,
    public_app_signup,
)
from commerce import views as commerce_views
from . import dynamic_alias_views

urlpatterns = [
    # Legacy/existing endpoints
    path("home/", app_home),
    path("app/bootstrap/", enterprise_app_bootstrap, name="enterprise_app_bootstrap"),
    path("app/dashboard/", enterprise_dashboard, name="enterprise_dashboard"),
    path("app/parties/", enterprise_parties, name="enterprise_parties"),
    path("app/customers/", enterprise_customers, name="enterprise_customers"),
    path("app/customers/<int:party_id>/", enterprise_customer_detail, name="enterprise_customer_detail"),
    path("app/products/", enterprise_products, name="enterprise_products"),
    path("app/products/<int:product_id>/", enterprise_product_detail, name="enterprise_product_detail"),
    path("app/invoices/", enterprise_invoices, name="enterprise_invoices"),
    path("app/transactions/", enterprise_transactions, name="enterprise_transactions"),
    path('login/', login_api),
    path('demo-login/', public_demo_login),
    path('app-signup/', public_app_signup),
    
    # Offline-first mobile sync (Flutter app)
    # Full URL: /api/v1/mobile/sync/push/ and /api/v1/mobile/sync/pull/
    path("v1/mobile/sync/push/", mobile_sync_push),
    path("v1/mobile/sync/pull/", mobile_sync_pull),

    # Dynamic Flutter ERP aliases.
    # These mirror the FastAPI engine at /fastapi/mobile/* while preserving
    # the requested /api/mobile/* URL shape for mobile clients and Postman.
    path("mobile/bootstrap/", dynamic_alias_views.bootstrap, name="mobile_dynamic_bootstrap"),
    path("mobile/current-user/", dynamic_alias_views.current_user, name="mobile_dynamic_current_user"),
    path("mobile/app-config/", dynamic_alias_views.app_config, name="mobile_dynamic_app_config"),
    path("mobile/modules/", dynamic_alias_views.modules, name="mobile_dynamic_modules"),
    path("mobile/dashboard-buttons/", dynamic_alias_views.dashboard_buttons, name="mobile_dynamic_dashboard_buttons"),
    path("mobile/menu/", dynamic_alias_views.menu, name="mobile_dynamic_menu"),
    path("mobile/screen-metadata/<str:module>/", dynamic_alias_views.screen_metadata, name="mobile_dynamic_screen_metadata"),
    path("auth/me/", dynamic_alias_views.auth_me, name="central_auth_me"),
    path("features/", dynamic_alias_views.features, name="central_features"),
    path("realtime/", dynamic_alias_views.realtime, name="central_realtime"),
    
    # AI/QR/Shop endpoints
    path("ai/reorder-plan/", commerce_views.api_ai_reorder_plan),
    path("ai/reorder-plan/health", commerce_views.api_ai_reorder_plan_health),
    path("dashboard/reorder-summary/", commerce_views.api_dashboard_reorder_summary),
    path("dashboard/reorder-summary/health", commerce_views.api_dashboard_reorder_summary_health),
    path("ai/generate-po/", commerce_views.api_ai_generate_po),
    path("ai/voice-call/", api_start_ai_call),
    path("qr/generate/", api_generate_qr),
    path("shops/add/", api_add_shop),
    
    # ============================================================
    # NEW FLUTTER-SPECIFIC JSON API ENDPOINTS
    # ============================================================
    # User/Auth endpoints
    path("auth/user/profile/", api_user_profile, name="api_user_profile"),
    path("auth/user/permissions/", api_user_permissions, name="api_user_permissions"),
    
    # Dashboard
    path("dashboard/data/", api_dashboard_data, name="api_dashboard_data"),
    
    # Inventory
    path("inventory/products/", api_inventory_products, name="api_inventory_products"),
    
    # Billing
    path("billing/invoices/", api_billing_invoices, name="api_billing_invoices"),
    
    # CRM
    path("crm/parties/", api_crm_parties, name="api_crm_parties"),
    
    # Ledger/Transactions
    path("ledger/transactions/", api_transactions_list, name="api_transactions_list"),
    
    # Home route
    path("", app_home, name="api_home"),
]
