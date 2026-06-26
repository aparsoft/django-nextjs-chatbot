import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from . import django_setup

# Collect all WebSocket URL patterns from apps
from chatbot.routing import websocket_urlpatterns as chatbot_ws_patterns

# JWT auth is handled inside ChatConsumer._authenticate() via ?token= query param.
# No session/auth middleware needed at the ASGI level.
application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": URLRouter(chatbot_ws_patterns),
    }
)
