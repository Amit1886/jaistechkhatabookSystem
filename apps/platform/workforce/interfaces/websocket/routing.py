from django.urls import path

from apps.platform.workforce.interfaces.websocket.consumers import WorkforceConsumer

websocket_urlpatterns = [
    path("ws/platform/workforce/events/", WorkforceConsumer.as_asgi()),
]

