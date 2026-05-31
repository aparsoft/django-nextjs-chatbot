import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.sessions import SessionMiddlewareStack
from . import django_setup

# Collect all WebSocket URL patterns from apps
from chatbot.routing import websocket_urlpatterns as chatbot_ws_patterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": SessionMiddlewareStack(
            AuthMiddlewareStack(
                URLRouter(
                    chatbot_ws_patterns,
                )
            )
        ),
    }
)
