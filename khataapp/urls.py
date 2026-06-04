from django.urls import path
from . import views
from . import views_bulk

app_name = "khataapp"

urlpatterns = [
    path("party/add/", views.add_party, name="add_party"),
    path("party/bulk-upload/", views_bulk.party_bulk_upload, name="party_bulk_upload"),
    path("party/sample-csv/", views_bulk.party_sample_csv, name="party_sample_csv"),
    path("party/list/", views.party_list, name="party_list"),
    path('party/view/<int:party_id>/', views.party_view, name='party_view'),
    path("party/edit/<int:party_id>/", views.edit_party, name="edit_party"),
    path("party/delete/<int:party_id>/", views.delete_party, name="delete_party"),
    path("credit-report/", views.credit_report_view, name="credit_report"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/update-plan/", views.update_plan, name="update_plan"),
    path("my-credits/", views.my_credits, name="my_credits"),
    path("transaction/add/", views.add_transaction, name="add_transaction"),
    path("transactions/bulk-upload/", views_bulk.transaction_bulk_upload, name="transaction_bulk_upload"),
    path("transactions/sample-csv/", views_bulk.transaction_sample_csv, name="transaction_sample_csv"),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/edit/<int:id>/',views.transaction_edit,name='transaction_edit'),
    path('transactions/view/<int:id>/', views.transaction_view, name='transaction_view'),
    path("transactions/delete/<int:id>/",views.transaction_delete,name="transaction_delete"),
    path("suppliers/dashboard/", views.supplier_dashboard, name="supplier_dashboard"),
    path("suppliers/<int:supplier_id>/", views.supplier_detail, name="supplier_detail"),
    path("suppliers/payments/add/", views.add_supplier_payment, name="add_supplier_payment"),
    path("agents/", views.agents_home, name="agents_home"),
    path("agents/manage/", views.field_agent_list, name="field_agent_list"),
    path("agents/create/", views.field_agent_create, name="field_agent_create"),
    path("agents/<int:agent_id>/edit/", views.field_agent_edit, name="field_agent_edit"),
    path("agents/<int:agent_id>/login-link/", views.field_agent_generate_link, name="field_agent_login_link"),
]
