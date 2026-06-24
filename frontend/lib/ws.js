// lib/ws.js  (client-only)
// WebSocket connection helper for real-time chat streaming.

/**
 * Open an authenticated WebSocket to the chat consumer.
 *
 * Backend protocol (server → client):
 *   { "type": "token",   "content": "..." }  — streaming chunk
 *   { "type": "message", "content": "..." }  — final complete message
 *   { "type": "error",   "content": "..." }  — error message
 *   { "type": "done" }                        — stream finished
 *
 * Backend protocol (client → server):
 *   { "message": "user text" }                — send a chat message
 *
 * @param {string} sessionId - Chat session UUID
 * @param {object} handlers - { onChunk, onMessage, onError, onClose }
 * @returns {Promise<WebSocket>} The open WebSocket connection
 */
export async function openChatSocket(sessionId, { onChunk, onMessage, onError, onClose } = {}) {
  const res = await fetch("/api/auth/ws-token");
  if (!res.ok) throw new Error("Not authenticated");
  const { token } = await res.json();

  const host = process.env.NEXT_PUBLIC_WS_HOST;
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${host}/ws/chat/${sessionId}/?token=${token}`);

  ws.addEventListener("message", (e) => {
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }
    switch (data.type) {
      case "token":
        onChunk?.(data.content);
        break;
      case "message":
        onMessage?.(data.content);
        break;
      case "done":
        onClose?.();
        break;
      case "error":
        onError?.(data.content);
        break;
    }
  });

  ws.addEventListener("error", () => onError?.("Connection error"));
  ws.addEventListener("close", () => onClose?.());

  return ws;
}

/**
 * Send a chat message over an existing WebSocket connection.
 * Waits for the socket to be open before sending.
 */
export function sendChatMessage(ws, message) {
  const payload = JSON.stringify({ message });
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(payload);
  } else {
    ws.addEventListener("open", () => ws.send(payload), { once: true });
  }
}