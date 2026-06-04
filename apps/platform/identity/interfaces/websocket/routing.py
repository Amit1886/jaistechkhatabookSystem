from django.urls import path

from apps.platform.identity.interfaces.websocket.consumers import IdentityActivityConsumer

websocket_urlpatterns = [
    path("ws/platform/identity/activity/", IdentityActivityConsumer.as_asgi()),
]
