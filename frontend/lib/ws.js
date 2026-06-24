// lib/ws.js  (client-only)
// WebSocket helpers using react-use-websocket for robust connection management.
//
// Backend protocol (server → client):
//   { "type": "token",   "content": "..." }  — streaming chunk
//   { "type": "message", "content": "..." }  — final complete message
//   { "type": "error",   "content": "..." }  — error message
//   { "type": "done" }                        — stream finished
//
// Backend protocol (client → server):
//   { "message": "user text" }                — send a chat message

/**
 * Fetch a short-lived access token for WebSocket auth.
 * The BFF reads the httpOnly cookie and returns the token.
 * @returns {Promise<string>} The access token.
 */
export async function getWsToken() {
  const res = await fetch("/api/auth/ws-token");
  if (!res.ok) throw new Error("Not authenticated");
  const { token } = await res.json();
  return token;
}

/**
 * Build the WebSocket URL for a chat session.
 * @param {string} sessionId - Chat session UUID.
 * @param {string} token - JWT access token.
 * @returns {string} The ws:// or wss:// URL.
 */
export function buildWsUrl(sessionId, token) {
  const host = process.env.NEXT_PUBLIC_WS_HOST;
  const scheme =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "wss"
      : "ws";
  return `${scheme}://${host}/ws/chat/${sessionId}/?token=${token}`;
}

/**
 * Parse an incoming WebSocket message.
 * @param {MessageEvent} event - The raw WebSocket message event.
 * @returns {{ type: string, content?: string } | null}
 */
export function parseWsMessage(event) {
  try {
    return JSON.parse(event.data);
  } catch {
    return null;
  }
}

/**
 * Build the payload for sending a chat message.
 * @param {string} message - The user's message text.
 * @returns {string} JSON string.
 */
export function buildChatPayload(message) {
  return JSON.stringify({ message });
}
