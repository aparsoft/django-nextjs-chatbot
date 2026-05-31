"""
chatbot.consumers

WebSocket consumers for real-time chatbot interaction.

Consumers:
    ChatConsumer — WebSocket consumer for streaming chat via LangGraph agent.

Usage (frontend):
    const ws = new WebSocket(
        `ws://localhost:8000/ws/chat/${sessionId}/?token=${accessToken}`
    );
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // data.type: "message" | "token" | "error" | "done"
        // data.content: string (for message/token/error types)
    };
"""

from .chat_consumer import ChatConsumer

__all__ = ["ChatConsumer"]
