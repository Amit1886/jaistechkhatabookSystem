from django.urls import path
from . import views
from . import erp_views

app_name = 'reports'

urlpatterns = [
    path('transactions/', views.all_transactions, name='all_transactions'),
    path('cash-book/', views.cash_book, name='cash_book'),
    path("voucher-report/", views.voucher_report, name="voucher_report"),

    path('sales/', views.sales_report, name='sales_report'),
    path('purchase/', views.purchase_report, name='purchase_report'),
    path("quotations/", views.quotation_report, name="quotation_report"),

    path('stock-summary/', views.stock_summary, name='stock_summary'),
    path('low-stock/', views.low_stock, name='low_stock'),

    path('party-ledger/', views.party_ledger, name='party_ledger'),
    path('outstanding/', views.outstanding, name='outstanding'),

    path('profit-loss/', views.profit_loss, name='profit_loss'),
    path('day-book/', views.day_book, name='day_book'),
    path('audit-trail/', views.audit_trail, name='audit_trail'),

    # -----------------------------
    # ERP Accounting Reports (GL + StockLedger based)
    # -----------------------------
    path("erp/trial-balance/", erp_views.trial_balance, name="erp_trial_balance"),
    path("erp/profit-loss/", erp_views.profit_loss, name="erp_profit_loss"),
    path("erp/balance-sheet/", erp_views.balance_sheet, name="erp_balance_sheet"),
    path("erp/day-book/", erp_views.day_book, name="erp_day_book"),
    path("erp/cash-book/", erp_views.cash_book, name="erp_cash_book"),
    path("erp/bank-book/", erp_views.bank_book, name="erp_bank_book"),
    path("erp/ledger-statement/", erp_views.ledger_statement, name="erp_ledger_statement"),
    path("erp/party-outstanding/", erp_views.party_outstanding, name="erp_party_outstanding"),
    path("erp/stock/warehouse/", erp_views.warehouse_stock, name="erp_stock_warehouse"),
    path("erp/stock/product/<int:product_id>/", erp_views.product_movement, name="erp_stock_product_movement"),
    path("erp/gst/summary/", erp_views.gst_summary, name="erp_gst_summary"),

    # -----------------------------
    # Missing modules (UI wrappers)
    # -----------------------------
    path("account-summary/", views.account_summary, name="account_summary"),
    path("interest-calculation/", views.interest_calculation, name="interest_calculation"),
    path("inventory-books/", views.inventory_books, name="inventory_books"),
    path("inventory-summary/", views.inventory_summary, name="inventory_summary"),
    path("gst-report/", views.gst_report, name="gst_report"),
    path("mis-report/", views.mis_report, name="mis_report"),
    path("checklists/", views.checklist_list, name="checklist_list"),
    path("checklists/<int:checklist_id>/", views.checklist_detail, name="checklist_detail"),
    path("checklists/<int:checklist_id>/items/<int:item_id>/toggle/", views.checklist_item_toggle, name="checklist_item_toggle"),
    path("queries/", views.query_list, name="query_list"),
    path("queries/new/", views.query_create, name="query_create"),
    path("queries/<int:ticket_id>/", views.query_detail, name="query_detail"),
]
