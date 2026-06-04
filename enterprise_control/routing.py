from django.urls import re_path

from .consumers import EnterpriseStreamConsumer

websocket_urlpatterns = [
    re_path(r"ws/enterprise/(?P<stream>permissions|dashboard|modules)/$", EnterpriseStreamConsumer.as_asgi()),
]
