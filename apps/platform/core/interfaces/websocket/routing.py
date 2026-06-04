from django.urls import path

from apps.platform.core.interfaces.websocket.consumers import CoreEventConsumer

websocket_urlpatterns = [
    path("ws/platform/core/events/", CoreEventConsumer.as_asgi()),
]

