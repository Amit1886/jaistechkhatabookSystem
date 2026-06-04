from django.urls import path

from whatsapp import control_views, setup_views, views, visual_views

app_name = "whatsapp"

urlpatterns = [
    path("", control_views.whatsapp_control_center, name="control_center"),
    # Modern dashboard (simplified UI)
    path("dashboard/", views.whatsapp_accounting_dashboard, name="dashboard"),
    path("accounting/", views.whatsapp_accounting_dashboard, name="accounting_dashboard"),
    path("setup/", setup_views.whatsapp_setup_wizard, name="setup_wizard"),
    path("setup/poll/", setup_views.whatsapp_setup_poll, name="setup_poll"),
    path("mini/<uuid:account_id>/", control_views.whatsapp_mini_site, name="mini_site"),

    # User-side visual drag & drop bot builder (per WhatsApp account)
    path("accounts/<uuid:account_id>/visual-flows/", visual_views.visual_flow_list, name="visual_flow_list"),
    path(
        "accounts/<uuid:account_id>/visual-flows/<uuid:flow_id>/builder/",
        visual_views.visual_flow_builder,
        name="visual_flow_builder",
    ),
    path(
        "accounts/<uuid:account_id>/visual-flows/<uuid:flow_id>/save/",
        visual_views.visual_flow_save,
        name="visual_flow_save",
    ),
]
