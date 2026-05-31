"""
WebSocket URL routing for the chatbot app.

Defines URL patterns for WebSocket consumers.
Consumers are mounted under ``ws/chat/`` via the ASGI application.
"""

from django.urls import re_path

from .consumers.chat_consumer import ChatConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/chat/(?P<session_id>[0-9a-f-]+)/$",
        ChatConsumer.as_asgi(),
        name="ws-chat",
    ),
]
