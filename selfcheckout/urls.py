from django.urls import path
from .views import live_products

from . import views

app_name = "selfcheckout"

urlpatterns = [
    path("", views.kiosk, name="kiosk"),
    path("search/", views.product_search, name="search"),
    path("reset/", views.reset, name="reset"),
    path("queue/", views.queue_status, name="queue"),
    path("analytics/", views.interaction_dashboard, name="interaction_dashboard"),
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("digital-twin/", views.digital_twin_dashboard, name="digital_twin"),
    path("admin-broadcast/", views.admin_broadcast, name="admin_broadcast"),
    path("live-products/", live_products),
    path("mobile/<str:token>/", views.mobile_continue, name="mobile_continue"),
    path("queue/assign/", views.queue_assign, name="queue_assign"),
    path("recover-session/", views.recover_session, name="recover_session"),
    path("<uuid:session_key>/intelligence/", views.intelligence, name="intelligence"),
    path("<uuid:session_key>/retail-state/", views.retail_state, name="retail_state"),
    path("<uuid:session_key>/theme/", views.theme, name="theme"),
    path("<uuid:session_key>/support/", views.support_request, name="support"),
    path("<uuid:session_key>/interactions/", views.interaction_events, name="interaction_events"),
    path("<uuid:session_key>/mobile-handoff/", views.mobile_handoff, name="mobile_handoff"),
    path("<uuid:session_key>/reward-drop/", views.reward_drop, name="reward_drop"),
    path("<uuid:session_key>/idle/", views.idle, name="idle"),
    path("<uuid:session_key>/customer/send-otp/", views.customer_send_otp, name="customer_send_otp"),
    path("<uuid:session_key>/customer/verify-otp/", views.customer_verify_otp, name="customer_verify_otp"),
    path("<uuid:session_key>/customer/membership/", views.customer_membership, name="customer_membership"),
    path("<uuid:session_key>/customer/guest/", views.guest_checkout, name="guest_checkout"),
    path("<uuid:session_key>/cart/", views.cart, name="cart"),
    path("<uuid:session_key>/scan/", views.scan, name="scan"),
    path("<uuid:session_key>/voice/", views.voice_command, name="voice"),
    path("<uuid:session_key>/rfid/", views.rfid, name="rfid"),
    path("<uuid:session_key>/nfc-tap/", views.nfc_tap, name="nfc_tap"),
    path("<uuid:session_key>/health/", views.health, name="health"),
    path("<uuid:session_key>/items/<int:item_id>/update/", views.update_item, name="update_item"),
    path("<uuid:session_key>/items/<int:item_id>/remove/", views.remove_cart_item, name="remove_item"),
    path("<uuid:session_key>/pay/", views.pay, name="pay"),
]
