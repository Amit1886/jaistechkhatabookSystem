from django.urls import re_path

from .consumers import SelfCheckoutConsumer

websocket_urlpatterns = [
    re_path(r"ws/self-checkout/(?P<session_key>[0-9a-f-]+)/$", SelfCheckoutConsumer.as_asgi()),
]
