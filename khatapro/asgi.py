"""
ASGI config for khatapro project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

if os.name == "nt":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("DESKTOP_MODE", "1")
    os.environ.setdefault("LIGHTWEIGHT_DEPLOYMENT", "1")
    os.environ.setdefault("KP_APP_DATA_DIR", os.path.join(BASE_DIR, "_appdata", "Billentra"))
    os.environ.setdefault(
        "KP_DESKTOP_LOG_FILE",
        os.path.join(BASE_DIR, "_appdata", "Billentra", "logs", "desktop.log"),
    )

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")

django_asgi_app = get_asgi_application()

try:
    from starlette.applications import Starlette  # noqa: E402
    from starlette.routing import Mount  # noqa: E402
    from fastapi_app.main import app as fastapi_enterprise_app  # noqa: E402
except ModuleNotFoundError:
    Starlette = None
    Mount = None
    fastapi_enterprise_app = None

import chatbot.routing  # noqa: E402
import api.websocket.routing  # noqa: E402
import realtime.routing  # noqa: E402
import system_mode.routing  # noqa: E402
import selfcheckout.routing  # noqa: E402
import enterprise_control.routing  # noqa: E402

websocket_urlpatterns = (
    chatbot.routing.websocket_urlpatterns
    + api.websocket.routing.websocket_urlpatterns
    + system_mode.routing.websocket_urlpatterns
    + realtime.routing.websocket_urlpatterns
    + selfcheckout.routing.websocket_urlpatterns
    + enterprise_control.routing.websocket_urlpatterns
)

if Starlette and Mount and fastapi_enterprise_app:
    http_application = Starlette(
        routes=[
            Mount("/fastapi", app=fastapi_enterprise_app),
            Mount("/", app=django_asgi_app),
        ]
    )
else:
    http_application = django_asgi_app

application = ProtocolTypeRouter(
    {
        "http": http_application,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
