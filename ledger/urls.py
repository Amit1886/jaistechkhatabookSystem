from django.urls import path

from . import views

app_name = "ledger"

urlpatterns = [
    path("receipt/", views.universal_receipt, name="receipt"),
    path("stock-transfers/", views.stock_transfer_list, name="stock_transfer_list"),
    path("stock-transfers/new/", views.stock_transfer_create, name="stock_transfer_create"),
    path("stock-transfers/<int:pk>/", views.stock_transfer_detail, name="stock_transfer_detail"),
    path("stock-transfers/<int:pk>/edit/", views.stock_transfer_edit, name="stock_transfer_edit"),
    path("stock-transfers/<int:pk>/post/", views.stock_transfer_post, name="stock_transfer_post"),
    path("stock-transfers/<int:pk>/cancel/", views.stock_transfer_cancel, name="stock_transfer_cancel"),
    path("journal-vouchers/", views.journal_voucher_list, name="journal_voucher_list"),
    path("journal-vouchers/new/", views.journal_voucher_create, name="journal_voucher_create"),
    path("journal-vouchers/<int:pk>/", views.journal_voucher_detail, name="journal_voucher_detail"),
    path("journal-vouchers/<int:pk>/edit/", views.journal_voucher_edit, name="journal_voucher_edit"),
    path("journal-vouchers/<int:pk>/post/", views.journal_voucher_post, name="journal_voucher_post"),
    path("journal-vouchers/<int:pk>/cancel/", views.journal_voucher_cancel, name="journal_voucher_cancel"),

    path("credit-notes/", views.credit_note_list, name="credit_note_list"),
    path("credit-notes/new/", views.return_note_create, {"note_type": "credit"}, name="credit_note_create"),
    path("debit-notes/", views.debit_note_list, name="debit_note_list"),
    path("debit-notes/new/", views.return_note_create, {"note_type": "debit"}, name="debit_note_create"),
    path("notes/<int:pk>/", views.return_note_detail, name="return_note_detail"),
    path("notes/<int:pk>/edit/", views.return_note_edit, name="return_note_edit"),
    path("notes/<int:pk>/post/", views.return_note_post, name="return_note_post"),
    path("notes/<int:pk>/cancel/", views.return_note_cancel, name="return_note_cancel"),
]
